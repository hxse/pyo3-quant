"""测试工具函数 - 数据映射相关"""

from dataclasses import dataclass
from typing import cast

import polars as pl
from pyo3_quant.backtest_engine.data_ops import (
    is_natural_mapping_column,
    strip_indicator_time_columns,
)


@dataclass(slots=True)
class MappedDataView:
    """测试专用的映射后数据视图。"""

    source: dict[str, pl.DataFrame]
    base_data_key: str


@dataclass(slots=True)
class MappedResultView:
    """测试专用的映射后结果视图。"""

    indicators: dict[str, pl.DataFrame] | None
    signals: pl.DataFrame | None
    backtest_result: pl.DataFrame | None
    performance: dict | None


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
    # 1. 映射 indicators（在 result_pack 中）
    mapped_indicators = {}
    if result_pack.indicators:
        for source_key, indicators_df in result_pack.indicators.items():
            mapped_indicators[source_key] = apply_mapping_to_dataframe(
                indicators_df, source_key, data_pack
            )

    # 2. 映射 source 数据（在 data_pack 中）
    # 包括 ohlcv_*、ha_* 等正式 source 数据
    mapped_source = {}
    for source_key, df in data_pack.source.items():
        mapped_source[source_key] = apply_mapping_to_dataframe(
            df, source_key, data_pack
        )

    # 中文注释：这些映射结果只用于手写信号计算，不再伪装成正式 pack object。
    mapped_data_pack = MappedDataView(
        source=mapped_source,
        base_data_key=data_pack.base_data_key,
    )

    mapped_result_pack = MappedResultView(
        indicators=cast(
            dict[str, pl.DataFrame] | None,
            strip_indicator_time_columns(mapped_indicators)
            if mapped_indicators
            else None,
        ),
        signals=result_pack.signals,
        backtest_result=result_pack.backtest_result,
        performance=result_pack.performance,
    )

    return mapped_data_pack, mapped_result_pack
