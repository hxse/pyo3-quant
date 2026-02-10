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
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    条件：close, ohlcv_1h, 0 x> ema_30..ema_100
    """
    close_s = get_mapped_ohlcv(mapped_data_container, "ohlcv_1h", "close")
    ema30_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")
    ema100_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_1")

    length = len(close_s)
    result = [False] * length
    active = False

    close = close_s.to_list()
    ema30 = ema30_s.to_list()
    ema100 = ema100_s.to_list()

    for i in range(length):
        val = close[i]
        low_b = ema30[i]
        high_b = ema100[i]

        if any(v is None or math.isnan(v) for v in [val, low_b, high_b]):
            active = False
            result[i] = False
            continue

        prev_val = close[i - 1] if i > 0 else None
        prev_low_b = ema30[i - 1] if i > 0 else None

        # 1. 检查瞬时交叉: prev_val <= prev_low_b AND val > low_b
        is_cross = False
        if (
            prev_val is not None
            and not math.isnan(prev_val)
            and prev_low_b is not None
            and not math.isnan(prev_low_b)
        ):
            if prev_val <= prev_low_b and val > low_b:
                is_cross = True

        # 2. 检查区间脱离: val >= high_b OR val <= low_b
        is_ooz = val >= high_b or val <= low_b

        if is_cross and not is_ooz:
            active = True
        elif is_ooz:
            active = False

        result[i] = active

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
