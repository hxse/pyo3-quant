"""DataFrame 处理工具函数"""

from dataclasses import dataclass
from typing import Optional
import polars as pl

from py_entry.types import (
    DataPack,
    ResultPack,
)


@dataclass(frozen=True)
class ExportDataPackSnapshot:
    """导出态 DataPack 快照。

    这里不再伪装成正式 DataPack。
    它只承载已经补齐 index/time/date 的导出视图，避免回写只读 pack 对象。
    """

    mapping: pl.DataFrame
    skip_mask: Optional[pl.DataFrame]
    source: dict[str, pl.DataFrame]
    base_data_key: str


@dataclass(frozen=True)
class ExportResultSnapshot:
    """导出态 ResultPack 快照。"""

    indicators: Optional[dict[str, pl.DataFrame]]
    signals: Optional[pl.DataFrame]
    backtest_result: Optional[pl.DataFrame]
    performance: Optional[dict[str, float]]


def reorder_columns(
    df: pl.DataFrame,
    priority_order: list[str],
) -> pl.DataFrame:
    """重新排列 DataFrame 的列顺序

    Args:
        df: 要处理的 DataFrame
        priority_order: 优先顺序的列名列表

    Returns:
        列顺序重新排列后的 DataFrame
    """
    current_columns = df.columns
    final_column_order = [col for col in priority_order if col in current_columns] + [
        col for col in current_columns if col not in priority_order
    ]
    return df.select(final_column_order)


def add_contextual_columns_to_dataframes(
    data_pack: Optional[DataPack],
    result: ResultPack,
    add_index: bool,
    add_time: bool,
    add_date: bool,
) -> tuple[Optional[ExportDataPackSnapshot], ExportResultSnapshot]:
    """为单个 ResultPack 中的所有 DataFrame 添加上下文列

    这里不会直接修改传入的 data_pack / result。
    正式 pack 类型已收口为只读对象，导出链只返回导出态快照。

    Args:
        data_pack: 数据包，包含 mapping, skip_mask, source 等字段
        result: 单个回测结果，包含 indicators, signals, backtest_result 等字段
        add_index: 是否添加索引列
        add_time: 是否添加时间列
        add_date: 是否添加日期列（ISO格式）
    """
    time_source_provider = None
    if data_pack is not None and data_pack.source is not None:
        # 这里必须先拿到“原始 source 快照”。
        # 注意：DataPack.source 在 pyo3 对象上通常返回的是拷贝字典，
        # 不能依赖原地修改 dict[key] 写回对象。
        time_source_provider = data_pack.source.copy()

    export_data_pack: Optional[ExportDataPackSnapshot] = None
    if data_pack is not None:
        processed_mapping = process_dataframe(
            data_pack.mapping,
            add_index,
            add_time,
            add_date,
            None,
            data_pack,
            time_source_provider,
        )
        processed_skip_mask = None
        if data_pack.skip_mask is not None:
            processed_skip_mask = process_dataframe(
                data_pack.skip_mask,
                add_index,
                add_time,
                add_date,
                None,
                data_pack,
                time_source_provider,
            )

        processed_source: dict[str, pl.DataFrame] = {}
        for key, df in data_pack.source.items():
            processed_source[key] = process_dataframe(
                df,
                add_index,
                add_time,
                add_date,
                key,
                data_pack,
                time_source_provider,
            )

        export_data_pack = ExportDataPackSnapshot(
            mapping=processed_mapping,
            skip_mask=processed_skip_mask,
            source=processed_source,
            base_data_key=data_pack.base_data_key,
        )

    # 中文注释：导出态 indicators 继续保留公开形态（携带 time 列），
    # 这里仅生成快照，不再写回 ResultPack。
    processed_indicators = None
    if result.indicators is not None:
        processed_indicators = {}
        for key, df in result.indicators.items():
            processed_indicators[key] = process_dataframe(
                df,
                add_index,
                add_time,
                add_date,
                key,
                data_pack,
                time_source_provider,
            )

    processed_signals = None
    if result.signals is not None and data_pack is not None:
        processed_signals = process_dataframe(
            result.signals,
            add_index,
            add_time,
            add_date,
            data_pack.base_data_key,
            data_pack,
            time_source_provider,
        )

    processed_backtest = None
    if result.backtest_result is not None and data_pack is not None:
        processed_backtest = process_dataframe(
            result.backtest_result,
            add_index,
            add_time,
            add_date,
            data_pack.base_data_key,
            data_pack,
            time_source_provider,
        )

    return (
        export_data_pack,
        ExportResultSnapshot(
            indicators=processed_indicators,
            signals=processed_signals,
            backtest_result=processed_backtest,
            performance=dict(result.performance)
            if result.performance is not None
            else None,
        ),
    )


def process_dataframe(
    df: pl.DataFrame,
    add_index: bool,
    add_time: bool,
    add_date: bool,
    source_key: Optional[str],
    data_pack: Optional[DataPack],
    time_source_provider: Optional[dict[str, pl.DataFrame]],
) -> pl.DataFrame:
    """处理单个DataFrame，添加指定的列

    Args:
        df: 要处理的DataFrame
        add_index: 是否添加索引列
        add_time: 是否添加时间列
        add_date: 是否添加日期列
        source_key: 数据源键名，用于确定时间列的来源
        data_pack: 数据包，用于获取时间数据
        time_source_provider: 一个未经修改的 source 字典副本，用于提供可靠的时间数据

    Returns:
        处理后的DataFrame
    """
    original_add_time = add_time
    if add_date:
        add_time = True

    result_df = df.clone()

    # 1. 确保 df 有 index 列，这是 join 的基础
    if "index" not in result_df.columns:
        result_df = result_df.with_row_index("index")

    # 2. 如果需要 time 或 date，就 join time 列
    if (
        "time" not in result_df.columns
        and add_time
        and data_pack is not None
        and time_source_provider is not None
    ):
        time_df_source = None
        if source_key and source_key in time_source_provider:
            time_df_source = time_source_provider[source_key]
        elif (
            data_pack.base_data_key and data_pack.base_data_key in time_source_provider
        ):
            time_df_source = time_source_provider[data_pack.base_data_key]

        if time_df_source is not None and "time" in time_df_source.columns:
            # 确保 time_df_source 也有 index 列
            if "index" not in time_df_source.columns:
                time_df_source = time_df_source.with_row_index("index")

            # 使用 join 精确合并
            result_df = result_df.join(
                time_df_source.select(["index", "time"]), on="index", how="left"
            )

    # 3. 计算 date 列
    if add_date and "date" not in result_df.columns and "time" in result_df.columns:
        result_df = result_df.with_columns(
            pl.col("time")
            .cast(pl.Datetime(time_unit="ms", time_zone="UTC"))
            .dt.strftime("%Y-%m-%d %H:%M:%S%.3f")
            .alias("date")
        )

    # 4. 如果最初未请求 index，则删除
    if not add_index and "index" in result_df.columns:
        result_df = result_df.drop("index")

    # 5. 如果最初未请求 time，则删除
    if not original_add_time and "time" in result_df.columns:
        result_df = result_df.drop("time")

    # 6. 确保最终的列顺序
    result_df = reorder_columns(result_df, ["index", "time", "date"])

    return result_df
