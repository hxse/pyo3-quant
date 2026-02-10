"""场景: 区间穿越 inclusive - 手写计算"""

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
    条件：rsi, ohlcv_15m, 0 x>= 30..70
    """
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
    length = len(rsi_s)
    result = [False] * length
    active = False

    # 转化为 list 方便操作
    rsi = rsi_s.to_list()

    for i in range(length):
        val = rsi[i]

        # NaN/Null 处理：状态重置为非活跃
        if val is None or math.isnan(val):
            active = False
            result[i] = False
            continue

        prev_val = rsi[i - 1] if i > 0 else None

        # 1. 检查瞬时穿越 (x>= 30): prev <= 30 AND curr >= 30
        is_cross = False
        if prev_val is not None and not math.isnan(prev_val):
            # 注意这里是 prev < 30 (严格小于，因为 prev=30 时已经满足 >=30，不视为 Cross)
            if prev_val < 30 and val >= 30:
                is_cross = True

        # 2. 检查区间脱离 (out_of_zone): val > 70 OR val < 30
        # x>= 宽松模式：边界值不触发失效，必须严格越过边界
        is_ooz = val > 70 or val < 30

        # 状态切换逻辑
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
