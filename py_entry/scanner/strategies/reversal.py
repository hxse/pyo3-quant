from typing import Final

import pandas as pd
from pydantic import BaseModel

from .base import StrategyProtocol, StrategySignal, ScanContext, StrategyCheckResult
from .registry import StrategyRegistry
from ..indicators import (
    calculate_cci,
    calculate_ema,
    calculate_macd,
)
import pandas_ta as ta


class ReversalStrategyConfig(BaseModel):
    """Reversal 策略配置"""

    ema_period: int = 20
    cci_period: int = 14
    cci_threshold: float = 80.0

    # 背离检测窗口
    divergence_window: int = 10

    # MACD 参数
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


@StrategyRegistry.register
class ReversalStrategy(StrategyProtocol):
    """策略二：极值背驰"""

    name: Final[str] = "reversal"

    def __init__(self, config: ReversalStrategyConfig | None = None):
        self.config = config or ReversalStrategyConfig()

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        ctx.validate_klines_existence(["5m", "1h", "1d", "1w"])

        df_5m = ctx.klines["5m"]
        df_1h = ctx.klines["1h"]
        df_1d = ctx.klines["1d"]
        df_1w = ctx.klines["1w"]

        # 检查是否满足做空条件 (抓顶)
        short_res = self._check_short_setup(df_5m, df_1h, df_1d, df_1w)
        if short_res:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=short_res["trigger"],
                summary=f"{ctx.symbol} 做空(背驰) | {short_res['trigger']}",
                detail_lines=short_res.get("details", []),
            )

        # 检查是否满足做多条件 (抓底) - 逻辑对称
        long_res = self._check_long_setup(df_5m, df_1h, df_1d, df_1w)
        if long_res:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=long_res["trigger"],
                summary=f"{ctx.symbol} 做多(背驰) | {long_res['trigger']}",
                detail_lines=long_res.get("details", []),
            )

        return None

    def _check_short_setup(
        self, df_5m, df_1h, df_1d, df_1w
    ) -> StrategyCheckResult | None:
        """检查顶部背驰做空机会"""
        # 1. 周线: 强势多头 (CCI > 80 + close > EMA)
        w_close = df_1w["close"]
        w_ema = calculate_ema(w_close, self.config.ema_period)
        w_cci = calculate_cci(
            df_1w["high"], df_1w["low"], w_close, self.config.cci_period
        )

        if len(w_close) < 3:
            return None
        if not (
            w_cci.iloc[-2] > self.config.cci_threshold
            and w_close.iloc[-2] > w_ema.iloc[-2]
        ):
            return None

        w_detail = f"[周线] CCI:{w_cci.iloc[-2]:.1f}(>80) + 均线上"

        # 2. 日线: 高位背离 (CCI > 80 + close > EMA + 顶背离)
        d_close = df_1d["close"]
        d_ema = calculate_ema(d_close, self.config.ema_period)
        d_cci = calculate_cci(
            df_1d["high"], df_1d["low"], d_close, self.config.cci_period
        )

        if len(d_close) < self.config.divergence_window + 2:
            return None

        # 基本条件
        if not (
            d_cci.iloc[-2] > self.config.cci_threshold
            and d_close.iloc[-2] > d_ema.iloc[-2]
        ):
            return None

        # Heuristic 极简背离检测
        is_divergence = self._check_divergence_heuristic(
            prices=df_1d["high"],
            indicator=d_cci,
            lookback=self.config.divergence_window,
            mode="high",
        )

        if not is_divergence:
            return None

        d_detail = "[日线] 高位背离 (Px新高 CCI未高)"

        # 3. 1小时: 动能转空 (MACD 蓝柱 < 0)
        h_close = df_1h["close"]
        _, _, h_hist = calculate_macd(
            h_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(h_close) < 3 or h_hist.iloc[-2] >= 0:
            return None

        h_detail = "[1h] MACD蓝柱 (动能转空)"

        # 4. 5分钟: 共振杀跌
        # 条件: MACD红转蓝(触发) + close < 5m EMA + close < 1h EMA + close > 日线 EMA
        m_close = df_5m["close"]
        m_ema = calculate_ema(m_close, self.config.ema_period)
        _, _, m_hist = calculate_macd(
            m_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(m_close) < 3:
            return None

        # MACD Trigger: 红转蓝 (上一个 > 0, 当前 < 0) -> 对应 [-3] > 0, [-2] < 0
        is_trigger = (m_hist.iloc[-3] > 0) and (m_hist.iloc[-2] < 0)

        if not is_trigger:
            return None

        # 价格位置过滤
        curr_price = m_close.iloc[-2]

        # 需要 5m EMA, 1h EMA, 1d EMA at CURRENT PRICE LEVEL
        # 注意: 跨周期比较需要拿最新的值
        ma_5m = m_ema.iloc[-2]
        ma_1h = compute_ma_latest(df_1h, self.config.ema_period)  # 工具函数? 或者直接取
        ma_1d = compute_ma_latest(df_1d, self.config.ema_period)

        cond_pos = (
            (curr_price < ma_5m) and (curr_price < ma_1h) and (curr_price > ma_1d)
        )

        if not cond_pos:
            return None

        m_detail = "MACD红转蓝 + 破位5m/1h + 撑于日线"

        trigger_msg = "5m背驰杀跌"

        return {
            "is_bullish": False,
            "is_bearish": True,
            "detail": trigger_msg,
            "price": curr_price,
            "extra_info": "",
            "trigger": trigger_msg,
            "details": [w_detail, d_detail, h_detail, f"[5m] {m_detail}"],
        }

    def _check_long_setup(
        self, df_5m, df_1h, df_1d, df_1w
    ) -> StrategyCheckResult | None:
        """检查底部背驰做多机会 (对称逻辑)"""
        # 1. 周线: 强势空头 (CCI < -80 + close < EMA)
        w_close = df_1w["close"]
        w_ema = calculate_ema(w_close, self.config.ema_period)
        w_cci = calculate_cci(
            df_1w["high"], df_1w["low"], w_close, self.config.cci_period
        )

        if len(w_close) < 3:
            return None
        if not (
            w_cci.iloc[-2] < -self.config.cci_threshold
            and w_close.iloc[-2] < w_ema.iloc[-2]
        ):
            return None

        w_detail = f"[周线] CCI:{w_cci.iloc[-2]:.1f}(<-80) + 均线下"

        # 2. 日线: 低位背离 (CCI < -80 + close < EMA + 底背离)
        d_close = df_1d["close"]
        d_ema = calculate_ema(d_close, self.config.ema_period)
        d_cci = calculate_cci(
            df_1d["high"], df_1d["low"], d_close, self.config.cci_period
        )

        if len(d_close) < self.config.divergence_window + 2:
            return None

        if not (
            d_cci.iloc[-2] < -self.config.cci_threshold
            and d_close.iloc[-2] < d_ema.iloc[-2]
        ):
            return None

        # Heuristic 极简背离检测
        is_divergence = self._check_divergence_heuristic(
            prices=df_1d["low"],
            indicator=d_cci,
            lookback=self.config.divergence_window,
            mode="low",
        )

        if not is_divergence:
            return None

        d_detail = "[日线] 低位背离 (Px新低 CCI未低)"

        # 3. 1小时: 动能转多 (MACD 红柱 > 0)
        h_close = df_1h["close"]
        _, _, h_hist = calculate_macd(
            h_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(h_close) < 3 or h_hist.iloc[-2] <= 0:
            return None

        h_detail = "[1h] MACD红柱 (动能转多)"

        # 4. 5分钟: 共振反弹
        # 条件: MACD蓝转红(触发) + close > 5m EMA + close > 1h EMA + close < 日线 EMA
        m_close = df_5m["close"]
        m_ema = calculate_ema(m_close, self.config.ema_period)
        _, _, m_hist = calculate_macd(
            m_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(m_close) < 3:
            return None

        is_trigger = (m_hist.iloc[-3] < 0) and (m_hist.iloc[-2] > 0)

        if not is_trigger:
            return None

        curr_price = m_close.iloc[-2]

        ma_5m = m_ema.iloc[-2]
        ma_1h = compute_ma_latest(df_1h, self.config.ema_period)
        ma_1d = compute_ma_latest(df_1d, self.config.ema_period)

        cond_pos = (
            (curr_price > ma_5m) and (curr_price > ma_1h) and (curr_price < ma_1d)
        )

        if not cond_pos:
            return None

        m_detail = "MACD蓝转红 + 站上5m/1h + 压于日线"
        trigger_msg = "5m背驰反弹"

        return {
            "is_bullish": True,
            "is_bearish": False,
            "detail": trigger_msg,
            "price": curr_price,
            "extra_info": "",
            "trigger": trigger_msg,
            "details": [w_detail, d_detail, h_detail, f"[5m] {m_detail}"],
        }

    def _check_divergence_heuristic(
        self,
        prices: pd.Series,
        indicator: pd.Series,
        lookback: int,
        mode: str = "high",
    ) -> bool:
        """
        极简背离检测 heuristic
        Top Divergence (mode='high'): Price New High + Indicator Not New High
        Bottom Divergence (mode='low'): Price New Low + Indicator Not New Low

        Args:
            prices: High or Low price series
            indicator: Indicator series (e.g. CCI)
            lookback: lookback window size
            mode: "high" for top divergence, "low" for bottom divergence
        """
        # slice ending at -1 (excluding current forming bar)
        # length of slice = lookback.
        # range: [-(lookback+1) : -1]

        if len(prices) < lookback + 2:
            return False

        subset_price = prices.iloc[-(lookback + 1) : -1]
        subset_ind = indicator.iloc[-(lookback + 1) : -1]

        curr_price = subset_price.iloc[-1]
        curr_ind = subset_ind.iloc[-1]

        if mode == "high":
            # Price is Highest in window
            price_is_extreme = curr_price >= subset_price.max()
            # Indicator is NOT Highest
            ind_not_extreme = curr_ind < subset_ind.max()
        else:
            # Price is Lowest
            price_is_extreme = curr_price <= subset_price.min()
            # Indicator is NOT Lowest
            # ind_not_extreme = curr_ind > subset_ind.min()
            # FIXED: Bottom Div logic -> Price Low, Ind Low?
            # Wait, Standard Bullish Div: Price New Low, Ind Higher Low (NOT New Low).
            # So Ind > Min. Correct.
            ind_not_extreme = curr_ind > subset_ind.min()

        return price_is_extreme and ind_not_extreme


def compute_ma_latest(df: pd.DataFrame, period: int) -> float:
    """辅助：计算最新EMA值"""
    if df is None or df.empty:
        return 0.0
    ema = ta.ema(df["close"], length=period)
    if ema is None or ema.empty:
        return 0.0
    return ema.iloc[-2]
