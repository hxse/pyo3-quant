"""
Heikin-Ashi 数据生成模块
"""
import polars as pl
import numpy as np

from .time_utils import time_format, fixed_cols


def calculate_heikin_ashi(df: pl.DataFrame) -> pl.DataFrame:
    """
    计算 Heikin-Ashi (平均K线),返回标准OHLCV格式

    Args:
        df: 包含 OHLC 数据的 DataFrame

    Returns:
        包含 time, date, open, high, low, close, volume 列的 DataFrame
    """
    # 提取 OHLC 数据为 numpy 数组(矢量化)
    open_arr = df["open"].to_numpy()
    high_arr = df["high"].to_numpy()
    low_arr = df["low"].to_numpy()
    close_arr = df["close"].to_numpy()

    # 计算 HA_Close(完全矢量化)
    ha_close = (open_arr + high_arr + low_arr + close_arr) / 4.0

    # 计算 HA_Open(递归关系,算法固有特性)
    # 初始化 HA_Open 数组
    ha_open = np.empty(len(df))
    ha_open[0] = (open_arr[0] + close_arr[0]) / 2.0

    # 使用 numpy 批量计算递归关系(最优化的算法实现)
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    # 计算 HA_High 和 HA_Low(完全矢量化)
    ha_high = np.maximum(np.maximum(high_arr, ha_open), ha_close)
    ha_low = np.minimum(np.minimum(low_arr, ha_open), ha_close)

    # 构建并返回标准OHLCV格式的 DataFrame
    result = pl.DataFrame(
        {
            "time": df["time"],
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
            "volume": df["volume"] if "volume" in df.columns else np.zeros(len(df)),
        }
    )

    # 添加 date 列
    result = result.with_columns(
        [
            pl.from_epoch(result["time"], time_unit="ms")
            .dt.replace_time_zone("UTC")
            .dt.strftime(time_format)
            .alias("date")
        ]
    )

    # 确保列顺序为: time, date, open, high, low, close, volume
    result = result.select(
        [
            pl.col(fixed_cols),  # time, date
            pl.col("*").exclude(fixed_cols),
        ]
    )

    return result


def generate_ha(ohlcv_dfs: list[pl.DataFrame]) -> list[pl.DataFrame]:
    """
    生成Heikin-Ashi数据,返回标准OHLCV格式

    Args:
        ohlcv_dfs: OHLCV DataFrame列表

    Returns:
        HA DataFrame列表,字段为: time, date, open, high, low, close, volume
    """
    return [calculate_heikin_ashi(df) for df in ohlcv_dfs]
