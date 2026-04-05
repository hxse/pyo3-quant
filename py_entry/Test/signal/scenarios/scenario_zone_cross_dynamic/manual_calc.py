"""场景: 区间穿越动态边界 - 手写计算"""

import math
import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    get_data_length,
    create_false_series,
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
    条件：close, ohlcv_15m, 0 x> ema_30..ema_100
    """
    close_s = get_mapped_ohlcv(mapped_data_pack, "ohlcv_15m", "close")
    ema30_s = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "ema_0")
    ema100_s = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "ema_1")

    length = len(close_s)
    result = [False] * length
    active = False

    close = close_s.to_list()
    ema30 = ema30_s.to_list()
    ema100 = ema100_s.to_list()

    for i in range(length):
        val = close[i]
        bound_a = ema30[i]
        bound_b = ema100[i]
        prev_val = close[i - 1] if i > 0 else None
        prev_bound_a = ema30[i - 1] if i > 0 else None
        prev_bound_b = ema100[i - 1] if i > 0 else None

        if any(
            v is None or math.isnan(v)
            for v in [val, bound_a, bound_b, prev_val, prev_bound_a, prev_bound_b]
        ):
            active = False
            result[i] = False
            continue

        assert prev_val is not None
        assert prev_bound_a is not None
        assert prev_bound_b is not None

        low = min(bound_a, bound_b)
        high = max(bound_a, bound_b)
        prev_low = min(prev_bound_a, prev_bound_b)
        is_in_zone = low <= val <= high
        is_cross = prev_val < prev_low and val >= low and is_in_zone

        if is_cross:
            active = True
        elif not is_in_zone:
            active = False

        result[i] = active

    return pl.Series("entry_long", result, dtype=pl.Boolean)


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
