"""场景: 区间穿越向上 - 手写计算"""

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
    条件：rsi, ohlcv_15m, 0 x> 30..70

    逻辑：
    - RSI 上穿 30 时激活
    - 如果已激活：
        - 如果 RSI >= 70 (终止边界) 或 RSI <= 30 (回落到激活边界以下)，则失效
    - 注意：如果 RSI 穿过 30 的瞬间同时也到达了 70 或回落（本场景 unlikely 但逻辑上要严密），则不激活
    """
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
    length = len(rsi_s)
    result = [False] * length
    active = False

    # 转化为 list 方便操作，polars Series 取值较慢
    rsi = rsi_s.to_list()

    for i in range(length):
        val = rsi[i]

        # NaN/Null 处理：状态重置为非活跃
        if val is None or math.isnan(val):
            active = False
            result[i] = False
            continue

        prev_val = rsi[i - 1] if i > 0 else None

        # 1. 检查瞬时穿越 (x> 30): prev <= 30 AND curr > 30
        is_cross = False
        if prev_val is not None and not math.isnan(prev_val):
            if prev_val <= 30 and val > 30:
                is_cross = True

        # 2. 检查区间脱离 (out_of_zone): val >= 70 OR val <= 30
        is_ooz = val >= 70 or val <= 30

        # 状态切换逻辑
        if is_cross and not is_ooz:
            active = True
        elif is_ooz:
            active = False

        # 如果当前 active 为 True 但当前值正好是激活边界或终止边界 (is_ooz)，则已经在上面处理为 False 了
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
