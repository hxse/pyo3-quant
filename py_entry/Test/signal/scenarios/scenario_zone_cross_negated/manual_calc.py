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
    注意：对于 NaN 数据，保持 False (或者不对比)，这将在 test_signal_generation.py 中通过 mask 进行处理。
    这里我们计算 Truth Table 即可。
    """
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
    length = len(rsi_s)
    result = [False] * length
    active = False

    # 转化为 list 方便操作
    rsi = rsi_s.to_list()

    for i in range(length):
        val = rsi[i]

        # NaN/Null 处理：
        # Engine 逻辑：NaN -> result=False -> negated -> result=True.
        # Mask 会标记这些位置为无效，但 assert_frame_equal 可能直接对比数值。
        # 为了匹配引擎的原始输出，这里 NaN 应该设为 True (即 not False)。
        if val is None or math.isnan(val):
            active = False
            result[i] = True  # negated False is True
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

        # 取反逻辑
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
