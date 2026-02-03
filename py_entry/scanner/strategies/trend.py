from typing import Final

import pandas as pd
from pydantic import BaseModel

from .base import StrategyProtocol, StrategySignal, ScanContext, StrategyCheckResult
from .registry import StrategyRegistry
from ..indicators import (
    calculate_cci,
    calculate_ema,
    calculate_macd,
    is_opening_bar,
    is_cross_above,
    is_cross_below,
    safe_iloc,
)


class TrendStrategyConfig(BaseModel):
    """Trend 策略配置 (内置)"""

    # 均线周期
    ema_period: int = 20

    # CCI 参数
    cci_period: int = 14
    cci_threshold_weekly: float = 80.0
    cci_threshold_daily: float = 30.0

    # MACD 参数 (用于小时级别)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # ER (Efficiency Ratio) 参数
    er_period: int = 14
    er_warning_threshold: float = 30.0
    er_warning_message: str = "大周期ER走弱，下调预期，建议5分钟1:2直接离场，别拿太久"


@StrategyRegistry.register
class TrendStrategy(StrategyProtocol):
    """策略一：强趋势共振"""

    name: Final[str] = "trend"

    def __init__(self, config: TrendStrategyConfig | None = None):
        self.config = config or TrendStrategyConfig()

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        """执行扫描逻辑"""
        # 1. 获取所需周期的 K线
        required_tfs = ["5m", "1h", "1d", "1w"]
        klines = {tf: ctx.get_klines(tf) for tf in required_tfs}

        ctx.validate_klines_existence(["5m", "1h", "1d", "1w"])

        df_5m = klines["5m"]
        df_1h = klines["1h"]
        df_1d = klines["1d"]
        df_1w = klines["1w"]

        # 2. 逐个周期检查
        # 结果容器
        results: list[dict] = []  # save details

        # Check 5m
        res_5m = self._check_5m(df_5m)  # type: ignore
        results.append({"tf": "5m", "res": res_5m})

        # Check 1h
        res_1h = self._check_1h(df_1h)  # type: ignore
        results.append({"tf": "1h", "res": res_1h})

        # Check 1d
        res_1d = self._check_1d(df_1d)  # type: ignore
        results.append({"tf": "1d", "res": res_1d})

        # Check 1w
        res_1w = self._check_1w(df_1w)  # type: ignore
        results.append({"tf": "1w", "res": res_1w})

        # 3. 综合判断
        is_long = all(r["res"]["is_bullish"] for r in results)
        is_short = all(r["res"]["is_bearish"] for r in results)

        if not is_long and not is_short:
            return None

        direction = "long" if is_long else "short"

        # 4. 生成信号内容
        # 触发信号就是 5m 的详情
        trigger = res_5m["detail"]

        # 详情行
        detail_lines = []
        for r in results:
            tf = r["tf"]
            res = r["res"]
            price = res["price"]
            text = res["detail"]
            if res.get("extra_info"):
                text += f" {res['extra_info']}"

            # 为了更好的可读性，我们可以把 tf 转为中文? 或者保持 5m, 1h
            detail_lines.append(f"[{tf} @ {price:.1f}] {text}")

        # 5. ER 警告检查 (只针对最大周期 1w)
        warnings = []
        er_msg = self._check_er(df_1w)  # type: ignore
        if er_msg:
            warnings.append(er_msg)
            # 同时也把 ER 值加到 1w 的详情里 (虽然上面已经通过 extra_info 加了，但 logic 需要理顺)
            # 在 check_1w 里加 extra_info 更合适

        return StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            direction=direction,
            trigger=trigger,
            summary=f"{ctx.symbol} {direction == 'long' and '做多' or '做空'} | {trigger}",
            detail_lines=detail_lines,
            warnings=warnings,
        )

    # === 内部检查逻辑 ===

    def _check_5m(self, df: pd.DataFrame) -> StrategyCheckResult:
        """检查 5分钟 (触发周期): close x> EMA"""
        close = df["close"]
        ema = calculate_ema(close, self.config.ema_period)

        # 基础数据检查
        if len(close) < 3 or ema.empty:
            return {
                "is_bullish": False,
                "is_bearish": False,
                "detail": "数据不足",
                "price": 0.0,
                "extra_info": "",
            }

        prev_close = safe_iloc(close, -2)

        is_bullish_cross = is_cross_above(close, ema)
        is_bearish_cross = is_cross_below(close, ema)

        # 开盘特殊处理
        is_opening = is_opening_bar(df, 300)  # 5m = 300s
        prev_above = prev_close > safe_iloc(ema, -2)
        prev_below = prev_close < safe_iloc(ema, -2)
        is_bullish_candle = prev_close > safe_iloc(df["open"], -2)
        is_bearish_candle = prev_close < safe_iloc(df["open"], -2)

        is_bullish = is_bullish_cross or (
            is_opening and is_bullish_candle and prev_above
        )
        is_bearish = is_bearish_cross or (
            is_opening and is_bearish_candle and prev_below
        )

        if is_bullish_cross:
            detail = "上穿EMA"
        elif is_bearish_cross:
            detail = "下穿EMA"
        elif is_opening and is_bullish_candle and prev_above:
            detail = "开盘阳线在EMA上"
        elif is_opening and is_bearish_candle and prev_below:
            detail = "开盘阴线在EMA下"
        else:
            detail = "未触发"

        # 如果是多头趋势，但没触发上穿（比如一直在上方），这里 is_bullish 会是 False
        # 因为 Trend 策略在 5m 级别要求的是 "Trigger" (Point of Action)

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "detail": detail,
            "price": prev_close,
            "extra_info": "",
        }

    def _check_1h(self, df: pd.DataFrame) -> StrategyCheckResult:
        """检查 1小时: MACD红柱 + close > EMA"""
        close = df["close"]
        ema = calculate_ema(close, self.config.ema_period)
        _, _, hist = calculate_macd(
            close, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
        )

        if len(close) < 3 or ema.empty or hist.empty:
            return {
                "is_bullish": False,
                "is_bearish": False,
                "detail": "数据不足",
                "price": 0.0,
                "extra_info": "",
            }

        prev_close = safe_iloc(close, -2)
        prev_hist = safe_iloc(hist, -2)
        prev_ema = safe_iloc(ema, -2)

        is_bullish = (prev_hist > 0) and (prev_close > prev_ema)
        is_bearish = (prev_hist < 0) and (prev_close < prev_ema)

        detail = (
            "MACD红+均线上"
            if is_bullish
            else ("MACD绿+均线下" if is_bearish else "无共振")
        )

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "detail": detail,
            "price": prev_close,
            "extra_info": "",
        }

    def _check_1d(self, df: pd.DataFrame) -> StrategyCheckResult:
        """检查 日线: CCI > 30 + close > EMA"""
        close = df["close"]
        ema = calculate_ema(close, self.config.ema_period)
        cci = calculate_cci(df["high"], df["low"], close, self.config.cci_period)

        if len(close) < 3 or ema.empty or cci.empty:
            return {
                "is_bullish": False,
                "is_bearish": False,
                "detail": "数据不足",
                "price": 0.0,
                "extra_info": "",
            }

        prev_close = safe_iloc(close, -2)
        prev_cci = safe_iloc(cci, -2)
        prev_ema = safe_iloc(ema, -2)

        is_bullish = (prev_cci > self.config.cci_threshold_daily) and (
            prev_close > prev_ema
        )
        is_bearish = (prev_cci < -self.config.cci_threshold_daily) and (
            prev_close < prev_ema
        )

        detail = (
            f"CCI:{prev_cci:.1f}+均线上"
            if is_bullish
            else (
                f"CCI:{prev_cci:.1f}+均线下"
                if is_bearish
                else f"CCI:{prev_cci:.1f}无共振"
            )
        )

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "detail": detail,
            "price": prev_close,
            "extra_info": "",
        }

    def _check_1w(self, df: pd.DataFrame) -> StrategyCheckResult:
        """检查 周线: CCI > 80 + close > EMA"""
        close = df["close"]
        ema = calculate_ema(close, self.config.ema_period)
        cci = calculate_cci(df["high"], df["low"], close, self.config.cci_period)

        if len(close) < 3 or ema.empty or cci.empty:
            return {
                "is_bullish": False,
                "is_bearish": False,
                "detail": "数据不足",
                "price": 0.0,
                "extra_info": "",
            }

        prev_close = safe_iloc(close, -2)
        prev_cci = safe_iloc(cci, -2)
        prev_ema = safe_iloc(ema, -2)

        # 计算ER用于展示 (extra_info)
        er_val = self._calculate_er(df)
        extra_info = f"ER:{er_val:.1f}" if er_val is not None else ""

        is_bullish = (prev_cci > self.config.cci_threshold_weekly) and (
            prev_close > prev_ema
        )
        is_bearish = (prev_cci < -self.config.cci_threshold_weekly) and (
            prev_close < prev_ema
        )

        detail = (
            f"CCI:{prev_cci:.1f}+均线上"
            if is_bullish
            else (
                f"CCI:{prev_cci:.1f}+均线下"
                if is_bearish
                else f"CCI:{prev_cci:.1f}无共振"
            )
        )

        return {
            "is_bullish": is_bullish,
            "is_bearish": is_bearish,
            "detail": detail,
            "extra_info": extra_info,
            "price": prev_close,
        }

    def _calculate_er(self, df: pd.DataFrame) -> float | None:
        """计算 ER"""
        try:
            er = df.ta.er(length=self.config.er_period)
            if er is None or er.empty:
                return None
            return safe_iloc(er, -2) * 100
        except Exception:
            return None

    def _check_er(self, df_1w: pd.DataFrame) -> str | None:
        """检查 ER 警告"""
        er_val = self._calculate_er(df_1w)
        if er_val is not None and er_val < self.config.er_warning_threshold:
            return self.config.er_warning_message
        return None
