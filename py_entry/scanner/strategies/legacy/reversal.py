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
from ..indicators import safe_iloc, get_recent_closed_window


class ReversalStrategyConfig(BaseModel):
    """Reversal 策略配置"""

    ema_period: int = 20
    cci_period: int = 14
    cci_threshold: float = 80.0

    # 背离检测参数
    divergence_window: int = 10  # 检测窗口大小
    divergence_idx_gap: int = 3  # 价格极值与CCI极值的最小idx差
    divergence_recency: int = 3  # 价格极值距离当前的最大idx差

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
            safe_iloc(w_cci, -2) > self.config.cci_threshold
            and safe_iloc(w_close, -2) > safe_iloc(w_ema, -2)
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
            safe_iloc(d_cci, -2) > self.config.cci_threshold
            and safe_iloc(d_close, -2) > safe_iloc(d_ema, -2)
        ):
            return None

        # Heuristic 极简背离检测
        is_divergence = self._check_divergence_heuristic(
            prices=df_1d["high"],
            indicator=d_cci,
            ema=d_ema,
            lookback=self.config.divergence_window,
            idx_gap_threshold=self.config.divergence_idx_gap,
            recency_threshold=self.config.divergence_recency,
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

        if len(h_close) < 3 or safe_iloc(h_hist, -2) >= 0:
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
        is_trigger = (safe_iloc(m_hist, -3) > 0) and (safe_iloc(m_hist, -2) < 0)

        if not is_trigger:
            return None

        # 价格位置过滤
        curr_price = safe_iloc(m_close, -2)

        # 需要 5m EMA, 1h EMA, 1d EMA at CURRENT PRICE LEVEL
        # 注意: 跨周期比较需要拿最新的值
        ma_5m = safe_iloc(m_ema, -2)
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
            safe_iloc(w_cci, -2) < -self.config.cci_threshold
            and safe_iloc(w_close, -2) < safe_iloc(w_ema, -2)
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
            safe_iloc(d_cci, -2) < -self.config.cci_threshold
            and safe_iloc(d_close, -2) < safe_iloc(d_ema, -2)
        ):
            return None

        # Heuristic 极简背离检测
        is_divergence = self._check_divergence_heuristic(
            prices=df_1d["low"],
            indicator=d_cci,
            ema=d_ema,
            lookback=self.config.divergence_window,
            idx_gap_threshold=self.config.divergence_idx_gap,
            recency_threshold=self.config.divergence_recency,
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

        if len(h_close) < 3 or safe_iloc(h_hist, -2) <= 0:
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

        is_trigger = (safe_iloc(m_hist, -3) < 0) and (safe_iloc(m_hist, -2) > 0)

        if not is_trigger:
            return None

        curr_price = safe_iloc(m_close, -2)

        ma_5m = safe_iloc(m_ema, -2)
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
        ema: pd.Series,
        lookback: int,
        idx_gap_threshold: int,
        recency_threshold: int,
        mode: str = "high",
    ) -> bool:
        """
        极简背离检测 heuristic v2
        1. 价格极值 idx 距离当前 < recency_threshold (近期见顶)
        2. 当前价格 > EMA (仍在均线上，未完全破位)
        3. 价格极值 idx - 指标极值 idx >= idx_gap_threshold (动能滞后/先见顶)
        """
        # slice ending at -1 (excluding current forming bar)
        if len(prices) < lookback + 2:
            return False

        subset_price = get_recent_closed_window(prices, lookback)
        subset_ind = get_recent_closed_window(indicator, lookback)

        # 窗口内最后一根的相对索引
        curr_idx = len(subset_price) - 1

        # 使用 safe_iloc 获取当前已完成K线的状态 (用于 EMA 确认)
        curr_price_val = safe_iloc(prices, -2)
        curr_ema_val = safe_iloc(ema, -2)

        if mode == "high":
            # 顶背离
            price_peak_idx = subset_price.argmax()  # 价格最高点索引
            ind_peak_idx = subset_ind.argmax()  # 指标最高点索引
            is_above_ema = curr_price_val > curr_ema_val
        else:
            # 底背离
            price_peak_idx = subset_price.argmin()
            ind_peak_idx = subset_ind.argmin()
            is_above_ema = curr_price_val < curr_ema_val  # 底背离要求在均线下

        # 条件1: 价格极值距离当前足够近 (避免很久前的背驰现在才报)
        recency_ok = (curr_idx - price_peak_idx) < recency_threshold

        # 条件2: 当前价格仍在均线上(做空前兆) / 下(做多前兆)
        # 确保趋势还没完全反转，抓的是"回落初期"
        ema_ok = is_above_ema

        # 条件3: 价格极值滞后于指标极值 (动能先衰)
        # 价格 idx > 指标 idx => 价格后见顶
        idx_gap = price_peak_idx - ind_peak_idx
        divergence_ok = (price_peak_idx > ind_peak_idx) and (
            idx_gap >= idx_gap_threshold
        )

        return recency_ok and ema_ok and divergence_ok


def compute_ma_latest(df: pd.DataFrame, period: int) -> float:
    """辅助：计算最新EMA值"""
    if df is None or df.empty:
        return 0.0
    ema = ta.ema(df["close"], length=period)
    if ema is None or ema.empty:
        return 0.0
    return safe_iloc(ema, -2)
