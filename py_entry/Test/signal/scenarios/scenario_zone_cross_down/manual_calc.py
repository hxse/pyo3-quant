"""场景: 区间穿越向下 - 手写计算"""

import math
import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_data_length,
    create_false_series,
    create_signal_dataframe,
)


def calculate_entry_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    条件：rsi, ohlcv_15m, 0 x< 70..30
    """
    rsi_s = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "rsi")
    length = len(rsi_s)
    result = [False] * length
    active = False

    rsi = rsi_s.to_list()

    for i in range(length):
        val = rsi[i]
        prev_val = rsi[i - 1] if i > 0 else None

        if val is None or math.isnan(val) or prev_val is None or math.isnan(prev_val):
            active = False
            result[i] = False
            continue

        low = min(70.0, 30.0)
        high = max(70.0, 30.0)
        is_in_zone = low <= val <= high
        is_cross = prev_val > high and val <= high and is_in_zone

        if is_cross:
            active = True
        elif not is_in_zone:
            active = False

        result[i] = active

    return pl.Series("entry_short", result, dtype=pl.Boolean)


def calculate_entry_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_exit_long(
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
    """计算所有信号"""
    return create_signal_dataframe(
        calculate_entry_long(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_exit_long(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_entry_short(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_exit_short(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
    )
