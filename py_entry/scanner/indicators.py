"""技术指标计算 - 使用 pandas-ta"""

import pandas as pd
import pandas_ta as ta


def calculate_ema(close: pd.Series, period: int) -> pd.Series:
    """计算 EMA"""
    return ta.ema(close, length=period)


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
    return ta.cci(high, low, close, length=period)


def is_cross_above(series: pd.Series, threshold: float | pd.Series) -> bool:
    """判断是否上穿（当前在上方，前一根在下方或相等）"""
    if len(series) < 2:
        return False
    curr = series.iloc[-1]
    prev = series.iloc[-2]

    if isinstance(threshold, pd.Series):
        if len(threshold) < 2:
            return False
        thresh_curr = threshold.iloc[-1]
        thresh_prev = threshold.iloc[-2]
    else:
        thresh_curr = thresh_prev = threshold

    return curr > thresh_curr and prev <= thresh_prev


def is_opening_bar(
    klines: pd.DataFrame, duration_seconds: int, tolerance_factor: float = 2.0
) -> bool:
    """检测是否为开盘第一根K线（通过时间间隙判断）"""
    if len(klines) < 2:
        return False

    curr_time = klines["datetime"].iloc[-1]
    prev_time = klines["datetime"].iloc[-2]

    # 计算时间间隔
    # 如果 datetime 是整数（天勤时间戳），直接差值；如果是 datetime 对象，需要转换
    if hasattr(curr_time, "timestamp"):
        gap = (curr_time - prev_time).total_seconds()
    else:
        # 假设是纳秒级或秒级时间戳 (int/float)
        gap = curr_time - prev_time

    # 如果间隔大于周期的 N 倍，说明中间有休市
    return gap > duration_seconds * tolerance_factor
