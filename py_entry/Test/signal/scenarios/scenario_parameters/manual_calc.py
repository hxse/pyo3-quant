"""场景: 参数引用 - 手写计算

手写模拟信号计算逻辑，验证参数引用是否正确
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
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
    entry_long: rsi_14 < $rsi_buy_threshold
    """
    # 提取数据
    rsi = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi_14")

    # 提取参数
    # signal_params 是 Dict[str, Param]
    threshold = signal_params["rsi_buy_threshold"].value

    # 计算条件
    # compare_series 支持标量作为 right_operand
    return compare_series(rsi, threshold, "<", offset_left=0)


def calculate_exit_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    exit_long: rsi_14 > $rsi_sell_threshold
    """
    rsi = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_sell_threshold"].value
    return compare_series(rsi, threshold, ">", offset_left=0)


def calculate_entry_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    entry_short: rsi_14 > $rsi_sell_threshold
    """
    rsi = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_sell_threshold"].value
    return compare_series(rsi, threshold, ">", offset_left=0)


def calculate_exit_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    exit_short: rsi_14 < $rsi_buy_threshold
    """
    rsi = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_buy_threshold"].value
    return compare_series(rsi, threshold, "<", offset_left=0)


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
