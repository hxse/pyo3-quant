"""测试工具函数 - 数据映射相关"""

import polars as pl
from pyo3_quant.backtest_engine.data_ops import is_natural_mapping_column


def extract_indicator_data(indicators_df, indicator_name):
    """从指标DataFrame中提取特定指标数据"""
    try:
        return indicators_df.select(indicator_name).to_series()
    except pl.exceptions.ColumnNotFoundError:
        raise ValueError(f"指标 {indicator_name} 未在DataFrame中找到")


def apply_mapping_if_needed(series, source_key, processed_data):
    """
    应用映射逻辑，与Rust端的apply_mapping_if_needed函数一致

    Args:
        series: 需要映射的Series
        source_key: 数据源键（如 "ohlcv_1h", "ohlcv_4h"）
        processed_data: DataContainer对象

    Returns:
        映射后的Series（如果需要映射）或原始Series（如果跳过映射）
    """
    if processed_data is None:
        return series

    # 中文注释：统一调用 Rust helper 判定自然序列 fast-path。
    if is_natural_mapping_column(processed_data, source_key):
        # 不需要映射，直接返回原始Series
        return series

    # 执行映射
    mapping_df = processed_data.mapping
    if source_key not in mapping_df.columns:
        raise ValueError(f"映射列 {source_key} 未在mapping中找到")

    # 获取映射索引并应用
    index_series = mapping_df[source_key].cast(pl.UInt32)
    return series.gather(index_series)


def apply_mapping_to_dataframe(df, source_key, processed_data):
    """
    对DataFrame中的所有列应用映射

    Args:
        df: 需要映射的DataFrame（indicators或ohlcv）
        source_key: 数据源键（如 "ohlcv_1h", "ohlcv_4h"）
        processed_data: DataContainer对象

    Returns:
        映射后的DataFrame
    """
    if processed_data is None:
        return df

    # 中文注释：统一调用 Rust helper 判定自然序列 fast-path。
    if is_natural_mapping_column(processed_data, source_key):
        return df

    # 对每一列应用映射
    mapped_columns = {}
    for col_name in df.columns:
        series = df[col_name]
        mapped_columns[col_name] = apply_mapping_if_needed(
            series, source_key, processed_data
        )

    return pl.DataFrame(mapped_columns)


def prepare_mapped_data(data_container, backtest_summary):
    """
    准备映射后的数据，用于手动信号计算

    Args:
        data_container: DataContainer对象（包含映射表和原始数据）
        backtest_summary: BacktestSummary对象（包含indicators）

    Returns:
        元组: (mapped_data_container, mapped_backtest_summary)
        - mapped_data_container: 映射后的DataContainer（所有source数据已映射到基准周期）
        - mapped_backtest_summary: 映射后的BacktestSummary（所有indicators已映射到基准周期）
    """
    from py_entry.types import DataContainer, BacktestSummary

    # 1. 映射 indicators（在 backtest_summary 中）
    mapped_indicators = {}
    if backtest_summary.indicators:
        for source_key, indicators_df in backtest_summary.indicators.items():
            mapped_indicators[source_key] = apply_mapping_to_dataframe(
                indicators_df, source_key, data_container
            )

    # 2. 映射 source 数据（在 data_container 中）
    # 包括 ohlcv_*, ha_*, renko_* 等所有数据
    mapped_source = {}
    for source_key, df in data_container.source.items():
        mapped_source[source_key] = apply_mapping_to_dataframe(
            df, source_key, data_container
        )

    # 3. 构造新的 DataContainer（映射后的）
    mapped_data_container = DataContainer(
        mapping=data_container.mapping,
        skip_mask=data_container.skip_mask,
        source=mapped_source,
        base_data_key=data_container.base_data_key,
    )

    # 4. 构造新的 BacktestSummary（映射后的）
    mapped_backtest_summary = BacktestSummary(
        performance=backtest_summary.performance,
        indicators=mapped_indicators,
        signals=backtest_summary.signals,  # signals 已经是映射后的
        backtest_result=backtest_summary.backtest_result,
    )

    return mapped_data_container, mapped_backtest_summary
