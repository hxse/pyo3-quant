"""技术指标计算 - 使用 pandas-ta"""

import pandas as pd
import pandas_ta as ta


def calculate_ema(close: pd.Series, period: int) -> pd.Series:
    """计算 EMA"""
    result = ta.ema(close, length=period)
    return result if result is not None else pd.Series(dtype=float)


def calculate_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算 MACD

    Returns:
        (MACD线, 信号线, 柱状图)
    """
    macd_df = ta.macd(close, fast=fast, slow=slow, signal=signal)
    if macd_df is None:
        # 数据不足时可能返回 None
        return pd.Series(), pd.Series(), pd.Series()

    # pandas-ta 返回 DataFrame，列名格式：MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    # 具体列名可能因版本略有不同，但通常符合命名规范
    # 为了稳健，直接按位置取或构造列名
    macd_col = f"MACD_{fast}_{slow}_{signal}"
    hist_col = f"MACDh_{fast}_{slow}_{signal}"
    signal_col = f"MACDs_{fast}_{slow}_{signal}"

    return macd_df[macd_col], macd_df[signal_col], macd_df[hist_col]


def calculate_cci(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """计算 CCI"""
    result = ta.cci(high, low, close, length=period)
    return result if result is not None else pd.Series(dtype=float)


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """计算 ADX"""
    # pandas-ta 的 adx 返回 DataFrame，包含 ADX, DMP, DMN
    result = ta.adx(high, low, close, length=period)

    if result is None:
        return pd.Series(dtype=float)

    # 列名通常是 ADX_14, DMP_14, DMN_14
    # 动态匹配列名
    adx_col = f"ADX_{period}"
    if adx_col in result.columns:
        return result[adx_col]

    return pd.Series(dtype=float)


def is_cross_above(series: pd.Series, threshold: float | pd.Series) -> bool:
    """判断上一根已完成K线是否上穿（基于[-2]和[-3]）"""
    if len(series) < 3:
        return False
    # 使用 [-2] (上一根已完成) 和 [-3] (上上根已完成)
    curr = series.iloc[-2]
    prev = series.iloc[-3]

    if isinstance(threshold, pd.Series):
        if len(threshold) < 3:
            return False
        thresh_curr = threshold.iloc[-2]
        thresh_prev = threshold.iloc[-3]
    else:
        thresh_curr = thresh_prev = threshold

    return curr > thresh_curr and prev <= thresh_prev


def is_cross_below(series: pd.Series, threshold: float | pd.Series) -> bool:
    """判断上一根已完成K线是否下穿（基于[-2]和[-3]）"""
    if len(series) < 3:
        return False
    # 使用 [-2] (上一根已完成) 和 [-3] (上上根已完成)
    curr = series.iloc[-2]
    prev = series.iloc[-3]

    if isinstance(threshold, pd.Series):
        if len(threshold) < 3:
            return False
        thresh_curr = threshold.iloc[-2]
        thresh_prev = threshold.iloc[-3]
    else:
        thresh_curr = thresh_prev = threshold

    return curr < thresh_curr and prev >= thresh_prev


def is_opening_bar(
    klines: pd.DataFrame, duration_seconds: int, tolerance_factor: float = 2.0
) -> bool:
    """检测上一根已完成K线是否为开盘第一根（通过[-2]和[-3]的时间间隙判断）"""
    if len(klines) < 3:
        return False

    # 比较 上一根完成K线([-2]) 与 上上根完成K线([-3]) 的时间差
    curr_time = klines["datetime"].iloc[-2]
    prev_time = klines["datetime"].iloc[-3]

    # 计算时间间隔
    # 天勤返回纳秒级时间戳，需转换为秒
    if hasattr(curr_time, "timestamp"):
        gap = (curr_time - prev_time).total_seconds()
    else:
        if hasattr(curr_time, "item"):
            curr_time = curr_time.item()

        # 处理可能的numpy类型
        if hasattr(prev_time, "item"):
            prev_time = prev_time.item()

        # 纳秒时间戳 sanity check: 应该大于 1e18 (约等于 2001-09-09)
        assert float(curr_time) > 1e18, f"时间戳似乎不是纳秒级: {curr_time}"

        # 安全转换和差值计算
        gap = (float(curr_time) - float(prev_time)) / 1e9

    # 如果间隔大于周期的 N 倍，说明中间有休市，则[-2]是新时段的第一根K线
    return gap > duration_seconds * tolerance_factor
