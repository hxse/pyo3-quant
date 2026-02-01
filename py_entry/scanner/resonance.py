from typing import Literal

import pandas as pd
from pydantic import BaseModel

from .config import IndicatorConfig, TimeframeConfig
from .indicators import (
    calculate_cci,
    calculate_ema,
    calculate_macd,
    is_opening_bar,
    is_cross_above,
    is_cross_below,
)


class TimeframeResonance(BaseModel):
    """单周期共振状态"""

    timeframe: str
    is_bullish: bool
    is_bearish: bool
    detail: str
    price: float = 0.0  # 当前价格（最新一根K线的收盘价）


class SymbolResonance(BaseModel):
    """品种共振结果"""

    symbol: str
    direction: Literal["long", "short", "none"]
    timeframes: list[TimeframeResonance]
    trigger_signal: str  # 主要触发信号


def check_crossover_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查穿越周期共振: close 上穿 EMA 或 开盘第一根阳线: close `>` EMA"""
    if len(klines) < config.ema_period + 2:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="数据不足",
        )

    close = klines["close"]
    ema = calculate_ema(close, config.ema_period)

    # 确保EMA计算出来了
    if ema.empty or ema.isna().iloc[-1] or ema.isna().iloc[-2]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    is_bullish_cross = is_cross_above(close, ema)
    is_bearish_cross = is_cross_below(close, ema)

    # 兼容此处变量名供下方使用
    curr_close = close.iloc[-1]
    curr_above = curr_close > ema.iloc[-1]
    curr_below = curr_close < ema.iloc[-1]

    # 开盘检测逻辑
    is_opening = is_opening_bar(klines, tf_config.seconds)
    is_bullish_candle = curr_close > klines["open"].iloc[-1]
    is_bearish_candle = curr_close < klines["open"].iloc[-1]

    # 符合条件：上穿 OR (开盘第一根阳线 且 在EMA上方)
    is_bullish = is_bullish_cross or (is_opening and is_bullish_candle and curr_above)
    # 符合条件：下穿 OR (开盘第一根阴线 且 在EMA下方)
    is_bearish = is_bearish_cross or (is_opening and is_bearish_candle and curr_below)

    # 细化触发信号
    if is_bullish_cross:
        cross_signal = "上穿EMA"
    elif is_bearish_cross:
        cross_signal = "下穿EMA"
    elif is_opening and is_bullish_candle and curr_above:
        cross_signal = "开盘阳线在EMA上"
    elif is_opening and is_bearish_candle and curr_below:
        cross_signal = "开盘阴线在EMA下"
    else:
        cross_signal = "未触发"

    detail = cross_signal
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=curr_close,
    )


def check_macd_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查 MACD 周期共振: MACD 红柱 (Diff-Dea > 0) 且 close > EMA"""
    if len(klines) < config.macd_slow + 2:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="数据不足",
        )

    close = klines["close"]
    ema = calculate_ema(close, config.ema_period)
    _, _, histogram = calculate_macd(
        close, config.macd_fast, config.macd_slow, config.macd_signal
    )

    if histogram.empty or ema.empty or histogram.isna().iloc[-1] or ema.isna().iloc[-1]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    is_red = histogram.iloc[-1] > 0
    curr_close = close.iloc[-1]
    above_ema = curr_close > ema.iloc[-1]

    is_bullish = is_red and above_ema

    is_green = histogram.iloc[-1] < 0
    below_ema = curr_close < ema.iloc[-1]
    is_bearish = is_green and below_ema

    detail = (
        "MACD红+均线上" if is_bullish else ("MACD绿+均线下" if is_bearish else "无共振")
    )
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=curr_close,
    )


def check_cci_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查 CCI 周期共振: CCI 绝对值 > 阈值 且 close 在 EMA 相应侧"""
    if len(klines) < config.cci_period + 2:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="数据不足",
        )

    high, low, close = klines["high"], klines["low"], klines["close"]
    ema = calculate_ema(close, config.ema_period)
    cci = calculate_cci(high, low, close, config.cci_period)

    if cci.empty or ema.empty or cci.isna().iloc[-1] or ema.isna().iloc[-1]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    cci_bullish = cci.iloc[-1] > config.cci_threshold
    # 空头对称逻辑：CCI < -阈值 (例如 < -30 或 < -80)
    cci_bearish = cci.iloc[-1] < -config.cci_threshold
    curr_close = close.iloc[-1]
    above_ema = curr_close > ema.iloc[-1]
    below_ema = curr_close < ema.iloc[-1]

    is_bullish = cci_bullish and above_ema
    is_bearish = cci_bearish and below_ema

    ema_status = "+均线上" if above_ema else ("+均线下" if below_ema else "")
    detail = f"CCI:{cci.iloc[-1]:.1f}{ema_status}"
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=curr_close,
    )


def check_timeframe_resonance(
    klines: pd.DataFrame,
    tf_config: TimeframeConfig,
    indicator_config: IndicatorConfig,
) -> TimeframeResonance:
    """通用周期共振检查"""
    if tf_config.check_type == "crossover":
        return check_crossover_resonance(klines, indicator_config, tf_config)
    elif tf_config.check_type == "macd":
        return check_macd_resonance(klines, indicator_config, tf_config)
    elif tf_config.check_type == "cci":
        return check_cci_resonance(klines, indicator_config, tf_config)
    else:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail=f"未知检查类型: {tf_config.check_type}",
        )
