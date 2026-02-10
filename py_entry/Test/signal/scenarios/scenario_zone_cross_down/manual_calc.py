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
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    条件：rsi, ohlcv_15m, 0 x< 70..30

    逻辑：
    - RSI 下穿 70 时激活
    - 如果已激活：
        - 如果 RSI <= 30 (终止边界) 或 RSI >= 70 (回升到激活边界以上)，则失效
    """
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
    length = len(rsi_s)
    result = [False] * length
    active = False

    rsi = rsi_s.to_list()

    for i in range(length):
        val = rsi[i]

        if val is None or math.isnan(val):
            active = False
            result[i] = False
            continue

        prev_val = rsi[i - 1] if i > 0 else None

        # 1. 检查瞬时穿越 (x< 70): prev >= 70 AND curr < 70
        is_cross = False
        if prev_val is not None and not math.isnan(prev_val):
            if prev_val >= 70 and val < 70:
                is_cross = True

        # 2. 检查区间脱离 (out_of_zone): val <= 30 OR val >= 70
        is_ooz = val <= 30 or val >= 70

        if is_cross and not is_ooz:
            active = True
        elif is_ooz:
            active = False

        result[i] = active

    return pl.Series("entry_short", result, dtype=pl.Boolean)


def calculate_entry_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_exit_long(
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
