"""
时间映射和序列检查模块
"""

import polars as pl
import numpy as np
from typing import Tuple, Dict


def is_natural_sequence(series: pl.Series) -> bool:
    """判断序列是否为从0开始的连续自然数列"""
    # 检查是否有 null 值
    if series.is_null().any():
        return False
    # 转换为 numpy 数组进行比较
    arr = series.to_numpy()
    expected = np.arange(len(arr))
    return np.array_equal(arr, expected)


def process_dataframe_mapping(
    base_df: pl.DataFrame,
    df: pl.DataFrame,
    col_name: str,
    result: pl.DataFrame,
    skip_mapping: Dict[str, bool],
) -> pl.DataFrame:
    """
    处理单个DataFrame的时间映射,包括创建索引、join_asof操作、检查自然序列、更新结果

    Args:
        base_df: 基准DataFrame,包含time列
        df: 需要映射的DataFrame
        col_name: 列名前缀(如"ohlcv_1", "ha_0", "renko_0")
        result: 当前的结果DataFrame
        skip_mapping: 跳过映射的字典

    Returns:
        更新后的结果DataFrame
    """
    # 提取前缀和索引
    prefix, idx = col_name.split("_")
    df_with_idx = df.select("time").with_columns(
        [pl.Series(f"idx_{prefix}_{idx}", np.arange(len(df)))]
    )
    mapping = (
        base_df.select("time")
        .join_asof(df_with_idx, on="time", strategy="backward")
        .select(pl.col(f"idx_{prefix}_{idx}"))
    )
    mapping_series = mapping.to_series()
    should_skip = is_natural_sequence(mapping_series)
    skip_mapping[col_name] = should_skip

    if not should_skip:
        result = result.with_columns([mapping_series.alias(col_name)])

    return result


def generate_time_mapping(
    ohlcv_dfs: list[pl.DataFrame],
    ha_dfs: list[pl.DataFrame] | None = None,
    renko_dfs: list[pl.DataFrame] | None = None,
) -> Tuple[pl.DataFrame, Dict[str, bool]]:
    """
    生成时间映射,将ohlcv[0]的time映射到所有其他DataFrame的索引

    Args:
        ohlcv_dfs: OHLCV DataFrame列表
        ha_dfs: HA DataFrame列表,可以为None
        renko_dfs: Renko DataFrame列表,可以为None

    Returns:
        元组:
        - 第一个返回值:只包含非跳过列的映射 DataFrame
        - 第二个返回值:字典,key 是列名(str),value 是是否跳过(bool),True 表示跳过
    """
    if not ohlcv_dfs:
        return pl.DataFrame(), {}

    base_df = ohlcv_dfs[0]
    skip_mapping = {}

    # ohlcv_0: 基准索引，默认就是从0开始的自然数列，必然会被跳过
    skip_mapping["ohlcv_0"] = True

    # 初始化一个空的 DataFrame 作为 result 的初始值
    result = pl.DataFrame()

    # 使用统一的循环结构处理所有DataFrame组
    dataframe_groups = [
        (ohlcv_dfs[1:], "ohlcv", 1),  # 从1开始
    ]

    # 只有当ha_dfs不为None时才添加到处理列表
    if ha_dfs is not None:
        dataframe_groups.append((ha_dfs, "ha", 0))

    # 只有当renko_dfs不为None时才添加到处理列表
    if renko_dfs is not None:
        dataframe_groups.append((renko_dfs, "renko", 0))

    for dfs, prefix, start_idx in dataframe_groups:
        for i, df in enumerate(dfs, start_idx):
            result = process_dataframe_mapping(
                base_df, df, f"{prefix}_{i}", result, skip_mapping
            )

    return result, skip_mapping
