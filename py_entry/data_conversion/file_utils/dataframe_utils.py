"""DataFrame 处理工具函数"""

from requests.utils import add_dict_to_cookiejar

from typing import Optional
import polars as pl

from py_entry.data_conversion.types import (
    DataContainer,
    BacktestSummary,
)


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


def add_contextual_columns_to_all_dataframes(
    data_dict: Optional[DataContainer],
    results: Optional[list[BacktestSummary]],
    add_index: bool,
    add_time: bool,
    add_date: bool,
) -> None:
    """为所有 DataFrame 添加列

    这个函数会直接修改传入的 data_dict 和 results 对象，为其中包含的所有 DataFrame 添加指定的列。

    Args:
        data_dict: 数据容器，包含 mapping, skip_mask, source 等字段
        results: 回测结果列表，每个结果包含 indicators, signals, backtest_result 等字段
        add_index: 是否添加索引列
        add_time: 是否添加时间列
        add_date: 是否添加日期列（ISO格式）
    """
    time_source_provider = None
    if data_dict is not None and data_dict.source is not None:
        # 创建一个 source 的浅拷贝，专门用于提供未经修改的时间列数据
        time_source_provider = data_dict.source.copy()

    if data_dict is not None:
        # 处理 mapping
        if data_dict.mapping is not None:
            data_dict.mapping = process_dataframe(
                data_dict.mapping,
                add_index,
                add_time,
                add_date,
                None,
                data_dict,
                time_source_provider,
            )

        # 处理 skip_mask
        if data_dict.skip_mask is not None:
            data_dict.skip_mask = process_dataframe(
                data_dict.skip_mask,
                add_index,
                add_time,
                add_date,
                None,
                data_dict,
                time_source_provider,
            )

        # 处理 source 中的所有 DataFrame
        if data_dict.source is not None:
            for key, df in data_dict.source.items():
                data_dict.source[key] = process_dataframe(
                    df,
                    add_index,
                    add_time,
                    add_date,
                    key,
                    data_dict,
                    time_source_provider,
                )

    # 处理 results 中的所有 DataFrame
    if results is not None:
        for summary in results:
            # 处理 indicators 中的所有 DataFrame
            if summary.indicators is not None:
                for key, df in summary.indicators.items():
                    summary.indicators[key] = process_dataframe(
                        df,
                        add_index,
                        add_time,
                        add_date,
                        key,
                        data_dict,
                        time_source_provider,
                    )

            # 处理 signals
            if summary.signals is not None and data_dict is not None:
                summary.signals = process_dataframe(
                    summary.signals,
                    add_index,
                    add_time,
                    add_date,
                    data_dict.BaseDataKey,
                    data_dict,
                    time_source_provider,
                )

            # 处理 backtest_result
            if summary.backtest_result is not None and data_dict is not None:
                summary.backtest_result = process_dataframe(
                    summary.backtest_result,
                    add_index,
                    add_time,
                    add_date,
                    data_dict.BaseDataKey,
                    data_dict,
                    time_source_provider,
                )


def process_dataframe(
    df: pl.DataFrame,
    add_index: bool,
    add_time: bool,
    add_date: bool,
    source_key: Optional[str],
    data_dict: Optional[DataContainer],
    time_source_provider: Optional[dict[str, pl.DataFrame]],
) -> pl.DataFrame:
    """处理单个DataFrame，添加指定的列

    Args:
        df: 要处理的DataFrame
        add_index: 是否添加索引列
        add_time: 是否添加时间列
        add_date: 是否添加日期列
        source_key: 数据源键名，用于确定时间列的来源
        data_dict: 数据容器，用于获取时间数据
        time_source_provider: 一个未经修改的 source 字典副本，用于提供可靠的时间数据

    Returns:
        处理后的DataFrame
    """
    original_add_time = add_time
    if add_date:
        add_time = True

    result_df = df

    # 1. 确保 df 有 index 列，这是 join 的基础
    if "index" not in result_df.columns:
        result_df = result_df.with_row_index("index")

    # 2. 如果需要 time 或 date，就 join time 列
    if (
        "time" not in result_df.columns
        and add_time
        and data_dict is not None
        and time_source_provider is not None
    ):
        time_df_source = None
        if source_key and source_key in time_source_provider:
            time_df_source = time_source_provider[source_key]
        elif data_dict.BaseDataKey and data_dict.BaseDataKey in time_source_provider:
            time_df_source = time_source_provider[data_dict.BaseDataKey]

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
