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
        processed_data: DataPack 对象

    Returns:
        映射后的Series（如果需要映射）或原始Series（如果跳过映射）
    """
    if processed_data is None:
        return series

    # 中文注释：统一调用 Rust helper 判定自然序列 fast-path。
    if is_natural_mapping_column(processed_data, source_key):
        # 不需要映射，直接返回原始Series
        return series

    # 中文注释：与 Rust resolve_data_operand 保持一致：
    # 非自然映射 source 在映射前先 lookback 一根，避免读取未收盘高周期 bar。
    series = series.shift(1)

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
        processed_data: DataPack 对象

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


def prepare_mapped_data(data_pack, result_pack):
    """
    准备映射后的数据，用于手动信号计算

    Args:
        data_pack: DataPack 对象（包含映射表和原始数据）
        result_pack: ResultPack 对象（包含 indicators）

    Returns:
        元组: (mapped_data_pack, mapped_result_pack)
        - mapped_data_pack: 映射后的 DataPack（所有 source 数据已映射到基准周期）
        - mapped_result_pack: 映射后的 ResultPack（所有 indicators 已映射到基准周期）
    """
    from py_entry.types import DataPack, ResultPack

    # 1. 映射 indicators（在 result_pack 中）
    mapped_indicators = {}
    if result_pack.indicators:
        for source_key, indicators_df in result_pack.indicators.items():
            mapped_indicators[source_key] = apply_mapping_to_dataframe(
                indicators_df, source_key, data_pack
            )

    # 2. 映射 source 数据（在 data_pack 中）
    # 包括 ohlcv_*, ha_*, renko_* 等所有数据
    mapped_source = {}
    for source_key, df in data_pack.source.items():
        mapped_source[source_key] = apply_mapping_to_dataframe(
            df, source_key, data_pack
        )

    # 3. 构造新的 DataPack（映射后的）
    mapped_data_pack = DataPack(
        mapping=data_pack.mapping,
        skip_mask=data_pack.skip_mask,
        source=mapped_source,
        base_data_key=data_pack.base_data_key,
        ranges=data_pack.ranges,
    )

    # 4. 构造新的 ResultPack（映射后的）
    mapped_result_pack = ResultPack(
        mapping=result_pack.mapping,
        ranges=result_pack.ranges,
        base_data_key=result_pack.base_data_key,
        performance=result_pack.performance,
        indicators=mapped_indicators,
        signals=result_pack.signals,  # signals 已经是映射后的
        backtest_result=result_pack.backtest_result,
    )

    return mapped_data_pack, mapped_result_pack
