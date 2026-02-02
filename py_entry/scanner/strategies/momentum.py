from typing import Final


from pydantic import BaseModel

from .base import StrategyProtocol, StrategySignal, ScanContext, StrategyCheckResult
from .registry import StrategyRegistry
from ..indicators import (
    calculate_ema,
    calculate_macd,
)


class MomentumStrategyConfig(BaseModel):
    """Momentum 策略配置"""

    ema_period: int = 20

    # MACD 参数
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


@StrategyRegistry.register
class MomentumStrategy(StrategyProtocol):
    """策略三：爆发动量"""

    name: Final[str] = "momentum"

    def __init__(self, config: MomentumStrategyConfig | None = None):
        self.config = config or MomentumStrategyConfig()

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        ctx.validate_klines_existence(["5m", "1h", "1d", "1w"])

        df_5m = ctx.klines["5m"]
        df_1h = ctx.klines["1h"]
        df_1d = ctx.klines["1d"]
        df_1w = ctx.klines["1w"]

        # 检查做多 (爆发)
        long_res = self._check_long_setup(df_5m, df_1h, df_1d, df_1w)
        if long_res:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=long_res["trigger"],
                summary=f"{ctx.symbol} 做多(动量) | {long_res['trigger']}",
                detail_lines=long_res.get("details", []),
            )

        # 检查做空 (跳水)
        short_res = self._check_short_setup(df_5m, df_1h, df_1d, df_1w)
        if short_res:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=short_res["trigger"],
                summary=f"{ctx.symbol} 做空(动量) | {short_res['trigger']}",
                detail_lines=short_res.get("details", []),
            )

        return None

    def _check_long_setup(
        self, df_5m, df_1h, df_1d, df_1w
    ) -> StrategyCheckResult | None:
        """检查动量做多 (起爆)"""
        # 1. 周线: 动能转强 (MACD柱强 + 连涨)
        w_close = df_1w["close"]
        if len(w_close) < 3:
            return None

        # MACD
        _, _, w_hist = calculate_macd(
            w_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )
        if w_hist.empty:
            return None

        # 动能转强: (蓝转红 OR 红变长) -> Hist[-2] > 0 and (Hist[-3] < 0 or Hist[-2] > Hist[-3])
        # 简化: Hist[-2] > Hist[-3] 且 Hist[-2] > 0 (如果是红变红) 或者 Hist[-2] > 0 (如果是蓝转红)
        # 综合: Hist[-2] > 0 且 Hist[-2] >= Hist[-3] (大致向上)
        w_hist_curr = w_hist.iloc[-2]
        w_hist_prev = w_hist.iloc[-3]
        macd_strong = (w_hist_curr > 0) and (w_hist_curr >= w_hist_prev)

        if not macd_strong:
            # 兼容 "蓝转红": w_hist_prev < 0 and w_hist_curr > 0
            if not (w_hist_prev < 0 and w_hist_curr > 0):
                return None

        # Price Action: 收阳 + close > close[1]
        w_open = df_1w["open"].iloc[-2]
        w_curr = w_close.iloc[-2]
        w_prev = w_close.iloc[-3]

        price_strong = (w_curr > w_open) and (w_curr > w_prev)

        if not price_strong:
            return None

        w_detail = "[周线] MACD增强 + K线连涨"

        # 2. 日线: 动能确认 (MACD红 + close > EMA)
        d_close = df_1d["close"]
        d_ema = calculate_ema(d_close, self.config.ema_period)
        _, _, d_hist = calculate_macd(
            d_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(d_close) < 3:
            return None
        if d_hist.iloc[-2] <= 0:
            return None
        if d_close.iloc[-2] <= d_ema.iloc[-2]:
            return None

        d_detail = "[日线] MACD红 + 均线上"

        # 3. 1小时: 零上红柱 (MACD > 0 and Hist > 0)
        h_close = df_1h["close"]
        h_diff, _, h_hist = calculate_macd(
            h_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(h_close) < 3:
            return None
        # 零上: Diff > 0; 红柱: Hist > 0
        if not (h_diff.iloc[-2] > 0 and h_hist.iloc[-2] > 0):
            return None

        h_detail = "[1h] 零上红柱 (空中加油)"

        # 4. 5分钟: 零上起爆 (触发)
        # 零上 (Diff > 0) 且 金叉/起爆 (Hist: 负->正)
        m_close = df_5m["close"]
        m_diff, _, m_hist = calculate_macd(
            m_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(m_close) < 3:
            return None

        # 必须在零上
        if m_diff.iloc[-2] <= 0:
            return None

        # 触发: 刚变红 (Hist[-3] <= 0 and Hist[-2] > 0)
        is_trigger = (m_hist.iloc[-3] <= 0) and (m_hist.iloc[-2] > 0)

        if not is_trigger:
            return None

        m_detail = "零上金叉/起爆"
        trigger_msg = "5m动量起爆"

        return {
            "is_bullish": True,
            "is_bearish": False,
            "detail": trigger_msg,
            "price": m_close.iloc[-2],
            "extra_info": "",
            "trigger": trigger_msg,
            "details": [w_detail, d_detail, h_detail, f"[5m] {m_detail}"],
        }

    def _check_short_setup(
        self, df_5m, df_1h, df_1d, df_1w
    ) -> StrategyCheckResult | None:
        """检查动量做空 (跳水)"""
        # 1. 周线
        w_close = df_1w["close"]
        if len(w_close) < 3:
            return None
        _, _, w_hist = calculate_macd(
            w_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )
        if w_hist.empty:
            return None

        w_hist_curr = w_hist.iloc[-2]
        w_hist_prev = w_hist.iloc[-3]

        # 动能转弱: (绿变更长 or 红转绿) -> Hist < 0 and (Hist <= Prev)
        macd_weak = (w_hist_curr < 0) and (w_hist_curr <= w_hist_prev)
        if not macd_weak:
            if not (w_hist_prev > 0 and w_hist_curr < 0):
                return None

        # Price: 收阴 + 跌破昨日
        w_open = df_1w["open"].iloc[-2]
        w_curr = w_close.iloc[-2]
        w_prev = w_close.iloc[-3]
        price_weak = (w_curr < w_open) and (w_curr < w_prev)

        if not price_weak:
            return None
        w_detail = "[周线] MACD走弱 + K线连跌"

        # 2. 日线
        d_close = df_1d["close"]
        d_ema = calculate_ema(d_close, self.config.ema_period)
        _, _, d_hist = calculate_macd(
            d_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(d_close) < 3:
            return None
        if d_hist.iloc[-2] >= 0:
            return None  # 绿柱
        if d_close.iloc[-2] >= d_ema.iloc[-2]:
            return None  # 均线下
        d_detail = "[日线] MACD绿 + 均线下"

        # 3. 1小时: 零下绿柱
        h_close = df_1h["close"]
        h_diff, _, h_hist = calculate_macd(
            h_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(h_close) < 3:
            return None
        if not (h_diff.iloc[-2] < 0 and h_hist.iloc[-2] < 0):
            return None
        h_detail = "[1h] 零下绿柱 (加速下跌)"

        # 4. 5分钟: 零下死叉
        m_close = df_5m["close"]
        m_diff, _, m_hist = calculate_macd(
            m_close,
            self.config.macd_fast,
            self.config.macd_slow,
            self.config.macd_signal,
        )

        if len(m_close) < 3:
            return None
        if m_diff.iloc[-2] >= 0:
            return None

        is_trigger = (m_hist.iloc[-3] >= 0) and (m_hist.iloc[-2] < 0)

        if not is_trigger:
            return None

        m_detail = "零下死叉/跳水"
        trigger_msg = "5m动量跳水"

        return {
            "is_bullish": False,
            "is_bearish": True,
            "detail": trigger_msg,
            "price": m_close.iloc[-2],
            "extra_info": "",
            "trigger": trigger_msg,
            "details": [w_detail, d_detail, h_detail, f"[5m] {m_detail}"],
        }
