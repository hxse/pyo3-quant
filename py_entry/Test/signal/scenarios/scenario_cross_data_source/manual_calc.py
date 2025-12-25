"""场景: 跨数据源和周期对比 - 手写计算

手写模拟跨数据源(ohlcv, ha, renko)和跨周期(15m, 1h, 4h)的指标对比
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    compare_series,
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
    Enter Long:
    1. ohlcv_15m SMA > renko_1h close  (跨数据源跨周期)
    2. ha_15m close > ohlcv_4h EMA     (跨数据源跨周期)
    3. renko_15m SMA > ha_1h close     (跨数据源跨周期)
    """
    # 条件1: ohlcv_15m SMA > renko_1h close
    sma_ohlcv_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "sma_0")
    close_renko_1h = get_mapped_ohlcv(mapped_data_container, "renko_1h", "close")
    cond1 = compare_series(sma_ohlcv_15m, close_renko_1h, ">", offset_left=0)

    # 条件2: ha_15m close > ohlcv_4h EMA
    close_ha_15m = get_mapped_ohlcv(mapped_data_container, "ha_15m", "close")
    ema_ohlcv_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "ema_0")
    cond2 = compare_series(close_ha_15m, ema_ohlcv_4h, ">", offset_left=0)

    # 条件3: renko_15m SMA > ha_1h close
    sma_renko_15m = get_mapped_indicator(mapped_backtest_summary, "renko_15m", "sma_0")
    close_ha_1h = get_mapped_ohlcv(mapped_data_container, "ha_1h", "close")
    cond3 = compare_series(sma_renko_15m, close_ha_1h, ">", offset_left=0)

    # 组合所有条件 (AND)
    # fill_null(False) 处理高周期数据开始阶段可能的空值
    final_cond = (
        cond1.fill_null(False) & cond2.fill_null(False) & cond3.fill_null(False)
    )

    return final_cond


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Exit Long:
    1. ohlcv_15m SMA < renko_1h close
    """
    sma_ohlcv_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "sma_0")
    close_renko_1h = get_mapped_ohlcv(mapped_data_container, "renko_1h", "close")

    return compare_series(sma_ohlcv_15m, close_renko_1h, "<", offset_left=0).fill_null(
        False
    )


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Enter Short:
    1. ha_15m close < ohlcv_4h EMA
    """
    close_ha_15m = get_mapped_ohlcv(mapped_data_container, "ha_15m", "close")
    ema_ohlcv_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "ema_0")

    return compare_series(close_ha_15m, ema_ohlcv_4h, "<", offset_left=0).fill_null(
        False
    )


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Exit Short:
    1. renko_15m SMA < ha_1h close
    """
    sma_renko_15m = get_mapped_indicator(mapped_backtest_summary, "renko_15m", "sma_0")
    close_ha_1h = get_mapped_ohlcv(mapped_data_container, "ha_1h", "close")

    return compare_series(sma_renko_15m, close_ha_1h, "<", offset_left=0).fill_null(
        False
    )


def calculate_signals(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.DataFrame:
    """
    计算所有信号并返回DataFrame
    """
    entry_long = calculate_entry_long(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    exit_long = calculate_exit_long(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    entry_short = calculate_entry_short(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    exit_short = calculate_exit_short(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )

    return create_signal_dataframe(entry_long, exit_long, entry_short, exit_short)
