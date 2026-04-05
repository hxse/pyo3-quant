"""场景: AND逻辑组合 - 手写计算

手写模拟 AND 逻辑组合计算
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    get_data_length,
    create_false_series,
    compare_series,
    create_signal_dataframe,
)


def calculate_entry_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    entry_long: (close > sma_20) AND (rsi_14 > 50)
    """
    # 从映射后的数据中提取
    close = get_mapped_ohlcv(mapped_data_pack, "ohlcv_15m", "close")
    sma = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "sma_20")
    rsi = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_threshold"].value

    # 条件1: close > sma
    cond1 = compare_series(close, sma, ">", offset_left=0)

    # 条件2: rsi > 50
    cond2 = compare_series(rsi, threshold, ">", offset_left=0)

    # 组合: AND
    return cond1 & cond2


def calculate_exit_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_entry_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_exit_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_signals(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.DataFrame:
    """
    计算所有信号并返回DataFrame
    """
    entry_long = calculate_entry_long(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    exit_long = calculate_exit_long(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    entry_short = calculate_entry_short(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    exit_short = calculate_exit_short(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )

    return create_signal_dataframe(entry_long, exit_long, entry_short, exit_short)
