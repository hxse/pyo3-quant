"""测试工具函数 - 数据准备相关"""

import polars as pl


def create_false_series(length: int) -> pl.Series:
    """
    创建指定长度的全False Series

    参数：
        length: Series长度

    返回：
        全False的布尔Series
    """
    return pl.Series([False] * length)


def get_mapped_indicator(
    mapped_backtest_summary, source_key: str, indicator_name: str
) -> pl.Series:
    """
    从映射后的BacktestSummary中提取指定指标的Series

    参数：
        mapped_backtest_summary: 映射后的BacktestSummary对象
        source_key: 数据源键（如 "ohlcv_15m", "ohlcv_1h", "ohlcv_4h"）
        indicator_name: 指标名称（如 "sma_0", "rsi_0"）

    返回：
        指标Series（已映射到基准周期）
    """
    if mapped_backtest_summary.indicators is None:
        raise ValueError("indicators 数据缺失")

    if source_key not in mapped_backtest_summary.indicators:
        raise KeyError(f"Source key '{source_key}' not found in indicators")

    indicators_df = mapped_backtest_summary.indicators[source_key]

    if indicator_name not in indicators_df.columns:
        raise KeyError(f"Indicator '{indicator_name}' not found in {source_key}")

    return indicators_df[indicator_name]


def get_mapped_ohlcv(
    mapped_data_container, source_key: str, column_name: str
) -> pl.Series:
    """
    从映射后的DataContainer中提取指定OHLCV列

    参数：
        mapped_data_container: 映射后的DataContainer对象
        source_key: 数据源键（如 "ohlcv_15m", "ha_15m", "renko_15m"）
        column_name: 列名（如 "close", "high", "low"）

    返回：
        OHLCV列Series（已映射到基准周期）
    """
    if source_key not in mapped_data_container.source:
        raise KeyError(f"Source key '{source_key}' not found in data_container")

    df = mapped_data_container.source[source_key]

    if column_name not in df.columns:
        raise KeyError(f"Column '{column_name}' not found in {source_key}")

    return df[column_name]


def get_data_length(mapped_data_container) -> int:
    """
    获取映射后数据的长度（基准周期的长度）

    参数：
        mapped_data_container: 映射后的DataContainer对象

    返回：
        数据长度
    """
    base_key = mapped_data_container.BaseDataKey
    if base_key not in mapped_data_container.source:
        raise KeyError(f"Base data key '{base_key}' not found in data_container")

    return len(mapped_data_container.source[base_key])
