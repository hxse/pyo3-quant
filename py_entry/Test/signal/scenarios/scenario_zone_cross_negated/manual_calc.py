"""场景: 取反区间穿越 - 手写计算"""

import math
import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_data_length,
    create_false_series,
    create_signal_dataframe,
)


def calculate_entry_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    条件：! rsi, ohlcv_15m, 0 x> 30..70
    逻辑：先计算 rsi x> 30..70，然后取反
    """
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
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

        low = min(30.0, 70.0)
        high = max(30.0, 70.0)
        is_in_zone = low <= val <= high
        is_cross = prev_val < low and val >= low and is_in_zone

        if is_cross:
            active = True
        elif not is_in_zone:
            active = False

        result[i] = not active

    return pl.Series("entry_long", result, dtype=pl.Boolean)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_signals(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.DataFrame:
    """计算所有信号"""
    return create_signal_dataframe(
        calculate_entry_long(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_exit_long(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_entry_short(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_exit_short(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
    )
