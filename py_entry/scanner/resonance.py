from typing import Literal

import pandas as pd
from pydantic import BaseModel

from .config import IndicatorConfig, TimeframeConfig, ScannerConfig
from .indicators import (
    calculate_cci,
    calculate_ema,
    calculate_macd,
    calculate_adx,
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
    extra_info: str | None = None  # 附加信息 (如 ADX 值)


class SymbolResonance(BaseModel):
    """品种共振结果"""

    symbol: str
    direction: Literal["long", "short", "none"]
    timeframes: list[TimeframeResonance]
    trigger_signal: str  # 主要触发信号
    adx_warning: str | None = None  # ADX 警告


def check_crossover_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查穿越周期共振: close 上穿 EMA 或 开盘第一根阳线: close `>` EMA (基于上一根已完成K线)"""
    # 需要至少3根数据才能计算 is_cross (-3, -2)
    if len(klines) < max(config.ema_period + 2, 3):
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="数据不足",
        )

    close = klines["close"]
    ema = calculate_ema(close, config.ema_period)

    # 确保EMA计算出来了 (检查最后完成的一根 [-2])
    if ema.empty or ema.isna().iloc[-2]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    # is_cross_above 内部已经改为检查 [-2] 和 [-3]
    is_bullish_cross = is_cross_above(close, ema)
    is_bearish_cross = is_cross_below(close, ema)

    # 获取上一根已完成K线的数据
    prev_close = close.iloc[-2]
    prev_above = prev_close > ema.iloc[-2]
    prev_below = prev_close < ema.iloc[-2]

    # 开盘检测逻辑 (内部检查 [-2] 和 [-3] 的时间间隔)
    is_opening = is_opening_bar(klines, tf_config.seconds)

    # 阳线/阴线判断 (基于上一根已完成K线 [-2])
    # 注意: iloc[-2] 的 close 和 open 都是确定的收盘值
    is_bullish_candle = prev_close > klines["open"].iloc[-2]
    is_bearish_candle = prev_close < klines["open"].iloc[-2]

    # 符合条件：上穿 OR (开盘第一根阳线 且 在EMA上方)
    is_bullish = is_bullish_cross or (is_opening and is_bullish_candle and prev_above)
    # 符合条件：下穿 OR (开盘第一根阴线 且 在EMA下方)
    is_bearish = is_bearish_cross or (is_opening and is_bearish_candle and prev_below)

    # 细化触发信号
    if is_bullish_cross:
        cross_signal = "上穿EMA"
    elif is_bearish_cross:
        cross_signal = "下穿EMA"
    elif is_opening and is_bullish_candle and prev_above:
        cross_signal = "开盘阳线在EMA上"
    elif is_opening and is_bearish_candle and prev_below:
        cross_signal = "开盘阴线在EMA下"
    else:
        cross_signal = "未触发"

    detail = cross_signal
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=prev_close,  # 返回已完成K线的价格
    )


def check_macd_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查 MACD 周期共振: MACD 红柱 (Diff-Dea > 0) 且 close > EMA (基于上一根已完成K线)"""
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

    # 检查上一根已完成K线 [-2] 的数据有效性
    if histogram.empty or ema.empty or histogram.isna().iloc[-2] or ema.isna().iloc[-2]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    # 使用 [-2] 数据
    is_red = histogram.iloc[-2] > 0
    prev_close = close.iloc[-2]
    above_ema = prev_close > ema.iloc[-2]

    is_bullish = is_red and above_ema

    is_green = histogram.iloc[-2] < 0
    below_ema = prev_close < ema.iloc[-2]
    is_bearish = is_green and below_ema

    detail = (
        "MACD红+均线上" if is_bullish else ("MACD绿+均线下" if is_bearish else "无共振")
    )
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=prev_close,
    )


def check_cci_resonance(
    klines: pd.DataFrame, config: IndicatorConfig, tf_config: TimeframeConfig
) -> TimeframeResonance:
    """检查 CCI 周期共振: CCI 绝对值 > 阈值 且 close 在 EMA 相应侧 (基于上一根已完成K线)"""
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

    # 检查上一根已完成K线 [-2] 的数据有效性
    if cci.empty or ema.empty or cci.isna().iloc[-2] or ema.isna().iloc[-2]:
        return TimeframeResonance(
            timeframe=tf_config.name,
            is_bullish=False,
            is_bearish=False,
            detail="指标数据不足",
        )

    # 使用 [-2] 数据
    cci_bullish = cci.iloc[-2] > config.cci_threshold
    # 空头对称逻辑：CCI < -阈值 (例如 < -30 或 < -80)
    cci_bearish = cci.iloc[-2] < -config.cci_threshold
    prev_close = close.iloc[-2]
    above_ema = prev_close > ema.iloc[-2]
    below_ema = prev_close < ema.iloc[-2]

    is_bullish = cci_bullish and above_ema
    is_bearish = cci_bearish and below_ema

    ema_status = "+均线上" if above_ema else ("+均线下" if below_ema else "")
    detail = f"CCI:{cci.iloc[-2]:.1f}{ema_status}"
    return TimeframeResonance(
        timeframe=tf_config.name,
        is_bullish=is_bullish,
        is_bearish=is_bearish,
        detail=detail,
        price=prev_close,
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


def get_adx_value(
    klines: pd.DataFrame,
    indicator_config: IndicatorConfig,
) -> float | None:
    """获取 ADX 值"""
    if len(klines) < indicator_config.adx_period + 2:
        return None

    high, low, close = (
        klines["high"],
        klines["low"],
        klines["close"],
    )
    adx = calculate_adx(high, low, close, indicator_config.adx_period)

    # 检查上一根已完成K线 [-2] 的数据有效性
    if adx.empty or adx.isna().iloc[-2]:
        return None

    return float(adx.iloc[-2])


def process_adx_for_largest_timeframe(
    klines_list: list[tuple[TimeframeConfig, pd.DataFrame]],
    details: list[TimeframeResonance],
    config: ScannerConfig,
) -> str | None:
    """
    处理最大周期的 ADX 逻辑：
    1. 找到最大周期
    2. 计算 ADX
    3. 更新该周期的 extra_info
    4. 只有当 ADX < warning_threshold 时，返回 warning_message

    Returns:
        warning_message (str) if triggered, else None
    """
    if not klines_list:
        return None

    # 1. 找到最大周期
    max_tf_idx, _ = get_largest_timeframe_index(klines_list)

    if max_tf_idx == -1:
        return None

    # 获取对应的数据和配置
    target_tf, target_df = klines_list[max_tf_idx]

    # 2. 计算 ADX
    adx_value = get_adx_value(target_df, target_tf.indicator)

    if adx_value is None:
        return None

    # 3. 更新详情显示
    if 0 <= max_tf_idx < len(details):
        details[max_tf_idx].extra_info = f"ADX:{adx_value:.1f}"

    # 4. 检查警告
    if adx_value < config.adx_warning_threshold:
        return config.adx_warning_message

    return None


def get_base_timeframe_config(timeframes: list[TimeframeConfig]) -> TimeframeConfig:
    """获取基础周期（最小周期），用于触发扫描"""
    if not timeframes:
        raise ValueError("Config timeframes is empty")
    return min(timeframes, key=lambda x: x.seconds)


def get_largest_timeframe_index(
    klines_list: list[tuple[TimeframeConfig, pd.DataFrame]],
) -> tuple[int, int]:
    """
    找到列表中最大周期的索引和秒数

    Returns:
        (index, seconds)
    """
    if not klines_list:
        return -1, -1

    best_idx = max(range(len(klines_list)), key=lambda i: klines_list[i][0].seconds)
    return best_idx, klines_list[best_idx][0].seconds
