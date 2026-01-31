from enum import Enum
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from .config import IndicatorConfig, TimeframeConfig
from .indicators import calculate_cci, calculate_ema, calculate_macd, is_opening_bar


class ResonanceLevel(Enum):
    """共振强度等级"""

    FIVE_STAR = 5  # 最优解：大盘+板块+品种都强趋势
    FOUR_STAR = 4  # 次优解：大盘非反向 + 板块+品种强趋势
    GARBAGE = 0  # 垃圾时间


class TimeframeResonance(BaseModel):
    """单周期共振状态"""

    timeframe: str
    is_bullish: bool
    is_bearish: bool
    detail: str


class SymbolResonance(BaseModel):
    """品种共振结果"""

    symbol: str
    direction: Literal["long", "short", "none"]
    level: ResonanceLevel
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
    if ema.isna().iloc[-1] or ema.isna().iloc[-2]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    curr_above = close.iloc[-1] > ema.iloc[-1]
    prev_above = close.iloc[-2] > ema.iloc[-2]
    is_cross_above = curr_above and not prev_above

    # 严格下穿逻辑: 当前在下方，且上一根不在下方
    curr_below = close.iloc[-1] < ema.iloc[-1]
    prev_below = close.iloc[-2] < ema.iloc[-2]
    is_cross_below = curr_below and not prev_below

    # 开盘检测逻辑
    is_opening = is_opening_bar(klines, tf_config.seconds)
    is_bullish_candle = close.iloc[-1] > klines["open"].iloc[-1]
    is_bearish_candle = close.iloc[-1] < klines["open"].iloc[-1]

    # 符合条件：上穿 OR (开盘第一根阳线 且 在EMA上方)
    is_bullish = is_cross_above or (is_opening and is_bullish_candle and curr_above)
    # 符合条件：下穿 OR (开盘第一根阴线 且 在EMA下方)
    is_bearish = is_cross_below or (is_opening and is_bearish_candle and curr_below)

    # 细化触发信号
    if is_cross_above:
        cross_signal = "上穿EMA"
    elif is_cross_below:
        cross_signal = "下穿EMA"
    elif is_opening and is_bullish and curr_above:
        cross_signal = "开盘阳线在EMA上"
    elif is_opening and is_bearish and curr_below:
        cross_signal = "开盘阴线在EMA下"
    else:
        cross_signal = "未触发"

    detail = f"close={close.iloc[-1]:.2f}, EMA={ema.iloc[-1]:.2f}, 状态={cross_signal}"
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
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
    above_ema = close.iloc[-1] > ema.iloc[-1]

    is_bullish = is_red and above_ema

    is_green = histogram.iloc[-1] < 0
    below_ema = close.iloc[-1] < ema.iloc[-1]
    is_bearish = is_green and below_ema

    detail = f"MACD柱={histogram.iloc[-1]:.4f}, close>EMA={above_ema}"
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
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
    cci_bearish = cci.iloc[-1] < -config.cci_threshold
    above_ema = close.iloc[-1] > ema.iloc[-1]
    below_ema = close.iloc[-1] < ema.iloc[-1]

    is_bullish = cci_bullish and above_ema
    is_bearish = cci_bearish and below_ema

    detail = f"CCI={cci.iloc[-1]:.2f}, close>EMA={above_ema}"
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
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


def classify_resonance_level(
    symbol_resonance: bool,
    sector_resonance: bool,
    market_resonance: bool,
    market_anti_resonance: bool,
) -> ResonanceLevel:
    """
    根据共振强度分级
    """
    if symbol_resonance and sector_resonance and market_resonance:
        return ResonanceLevel.FIVE_STAR
    elif symbol_resonance and sector_resonance and not market_anti_resonance:
        return ResonanceLevel.FOUR_STAR
    else:
        # 虽然共振了，但是大盘或板块不支持，视为垃圾时间或风险较大
        return ResonanceLevel.GARBAGE
