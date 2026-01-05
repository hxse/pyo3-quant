"""
深度追踪单笔交易的生命周期
对比 Pyo3 和 BTP 在每根 K 线的 TSL 计算和触发逻辑
"""

import numpy as np
import polars as pl
import pandas as pd
import talib
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp
from py_entry.Test.backtest.strategies.reversal_extreme.config import CONFIG as C
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def run_lifecycle_analysis():
    config = CommonConfig(
        bars=8000,
        seed=42,
        initial_capital=10000.0,
        commission=0.001,
        timeframe="15m",
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        allow_gaps=True,
        equity_cutoff_ratio=0.20,
    )

    print(f"=== 交易生命周期深度分析 ===\n")
    print(f"策略配置:")
    print(f"  sl_pct: {C.sl_pct}")
    print(f"  tp_atr: {C.tp_atr}")
    print(f"  tsl_atr: {C.tsl_atr}")
    print(f"  atr_period: {C.atr_period}")
    print(f"  sl_exit_in_bar: {C.sl_exit_in_bar}")
    print(f"  tp_exit_in_bar: {C.tp_exit_in_bar}")
    print(f"  sl_trigger_mode: {C.sl_trigger_mode} (True=High/Low)")
    print(f"  tsl_trigger_mode: {C.tsl_trigger_mode}")
    print(f"  tsl_anchor_mode: {C.tsl_anchor_mode} (True=Extremum)")
    print(f"  tsl_atr_tight: {C.tsl_atr_tight}")

    # 1. 运行引擎
    print("\n[1/4] 运行引擎...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")
    assert pyo3_adapter.result is not None

    ohlcv_df = generate_ohlcv_for_backtestingpy(config)
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)
    assert btp_adapter.result is not None

    # 2. 获取 OHLCV 和 ATR
    print("\n[2/4] 提取数据...")
    ohlc = ohlcv_df.copy()
    ohlc["ATR"] = talib.ATR(
        ohlc["High"].values,
        ohlc["Low"].values,
        ohlc["Close"].values,
        timeperiod=C.atr_period,
    )

    # 3. 提取交易
    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")
    btp_trades_raw = btp_adapter.result.stats["_trades"]

    # 找一个有差异的交易来分析 (Entry Bar 3340)
    TARGET_ENTRY_BAR = 3340

    print(f"\n[3/4] 分析目标交易 (Entry Bar {TARGET_ENTRY_BAR})...")

    # Pyo3 交易信息
    pyo3_entry = pyo3_df.filter(pl.col("bar_index") == TARGET_ENTRY_BAR).row(
        0, named=True
    )
    direction = "Long" if pyo3_entry["first_entry_side"] == 1 else "Short"
    entry_price = (
        pyo3_entry["entry_long_price"]
        if direction == "Long"
        else pyo3_entry["entry_short_price"]
    )

    # 找 Pyo3 exit
    if direction == "Long":
        pyo3_exits = pyo3_df.filter(
            (pl.col("bar_index") >= TARGET_ENTRY_BAR)
            & pl.col("exit_long_price").is_not_nan()
        )
    else:
        pyo3_exits = pyo3_df.filter(
            (pl.col("bar_index") >= TARGET_ENTRY_BAR)
            & pl.col("exit_short_price").is_not_nan()
        )
    pyo3_exit_row = pyo3_exits.row(0, named=True)
    pyo3_exit_bar = pyo3_exit_row["bar_index"]
    pyo3_exit_price = (
        pyo3_exit_row["exit_long_price"]
        if direction == "Long"
        else pyo3_exit_row["exit_short_price"]
    )

    # BTP 交易信息
    btp_trade = btp_trades_raw[btp_trades_raw["EntryBar"] == TARGET_ENTRY_BAR].iloc[0]
    btp_exit_bar = btp_trade["ExitBar"]
    btp_exit_price = btp_trade["ExitPrice"]

    print(f"\n  方向: {direction}")
    print(f"  Entry Price: {entry_price:.4f}")
    print(f"  Pyo3 Exit: Bar {pyo3_exit_bar}, Price {pyo3_exit_price:.4f}")
    print(f"  BTP  Exit: Bar {btp_exit_bar}, Price {btp_exit_price:.4f}")

    # 4. 逐 Bar 追踪 TSL 演化
    print(f"\n[4/4] 逐 Bar 追踪 TSL 演化...")

    # 计算初始 SL
    signal_bar = TARGET_ENTRY_BAR
    signal_close = ohlc.iloc[signal_bar]["Close"]
    signal_high = ohlc.iloc[signal_bar]["High"]
    signal_low = ohlc.iloc[signal_bar]["Low"]
    signal_atr = ohlc.iloc[signal_bar]["ATR"]

    if direction == "Long":
        sl_fixed = signal_close * (1 - C.sl_pct)
        if C.tsl_atr > 0:
            if C.tsl_anchor_mode:
                tsl_init = signal_high - signal_atr * C.tsl_atr
            else:
                tsl_init = signal_close - signal_atr * C.tsl_atr
            initial_sl = max(sl_fixed, tsl_init)
        else:
            initial_sl = sl_fixed
        extremum = signal_high if C.tsl_anchor_mode else signal_close
    else:
        sl_fixed = signal_close * (1 + C.sl_pct)
        if C.tsl_atr > 0:
            if C.tsl_anchor_mode:
                tsl_init = signal_low + signal_atr * C.tsl_atr
            else:
                tsl_init = signal_close + signal_atr * C.tsl_atr
            initial_sl = min(sl_fixed, tsl_init)
        else:
            initial_sl = sl_fixed
        extremum = signal_low if C.tsl_anchor_mode else signal_close

    print(f"\n  初始计算:")
    print(f"    Signal Close: {signal_close:.4f}")
    print(f"    Signal High:  {signal_high:.4f}")
    print(f"    Signal Low:   {signal_low:.4f}")
    print(f"    Signal ATR:   {signal_atr:.4f}")
    print(f"    SL Fixed:     {sl_fixed:.4f}")
    print(f"    TSL Init:     {tsl_init:.4f}")
    print(f"    Initial SL:   {initial_sl:.4f}")
    print(f"    Extremum:     {extremum:.4f}")

    # 逐 Bar 追踪
    current_sl = initial_sl
    trade_end = max(pyo3_exit_bar, btp_exit_bar) + 2

    print(f"\n  逐 Bar TSL 演化 (Entry+1 到 Exit):")
    print(
        f"  {'Bar':<6} {'High':<10} {'Low':<10} {'Close':<10} {'ATR':<10} {'Extremum':<12} {'TSL Price':<12} {'Current SL':<12} {'Trigger?':<10}"
    )

    for bar_idx in range(TARGET_ENTRY_BAR + 1, min(trade_end, len(ohlc))):
        bar = ohlc.iloc[bar_idx]
        prev_bar = ohlc.iloc[bar_idx - 1]

        # 更新 Extremum (使用 prev_bar)
        if C.tsl_anchor_mode:
            if direction == "Long":
                if prev_bar["High"] > extremum:
                    extremum = prev_bar["High"]
            else:
                if prev_bar["Low"] < extremum:
                    extremum = prev_bar["Low"]
        else:
            # Close mode
            if direction == "Long":
                if prev_bar["Close"] > extremum:
                    extremum = prev_bar["Close"]
            else:
                if prev_bar["Close"] < extremum:
                    extremum = prev_bar["Close"]

        # 计算 TSL Price
        prev_atr = ohlc.iloc[bar_idx - 1]["ATR"]
        if direction == "Long":
            tsl_price = extremum - prev_atr * C.tsl_atr
            new_sl = max(current_sl, tsl_price)
        else:
            tsl_price = extremum + prev_atr * C.tsl_atr
            new_sl = min(current_sl, tsl_price)

        # 检查触发
        if C.sl_trigger_mode:
            trigger_price = bar["Low"] if direction == "Long" else bar["High"]
        else:
            trigger_price = bar["Close"]

        if direction == "Long":
            triggered = trigger_price < new_sl
        else:
            triggered = trigger_price > new_sl

        trigger_str = "YES!" if triggered else ""

        # 标记 Exit Bar
        bar_label = f"{bar_idx}"
        if bar_idx == pyo3_exit_bar:
            bar_label += " (Pyo3)"
        if bar_idx == btp_exit_bar:
            bar_label += " (BTP)"

        print(
            f"  {bar_label:<6} {bar['High']:<10.4f} {bar['Low']:<10.4f} {bar['Close']:<10.4f} {bar['ATR']:<10.4f} {extremum:<12.4f} {tsl_price:<12.4f} {new_sl:<12.4f} {trigger_str:<10}"
        )

        current_sl = new_sl

        if bar_idx > trade_end:
            break

    # 5. 检查 Pyo3 的实际 SL 值
    print(f"\n[5/5] 检查 Pyo3 回测结果中的 SL 值...")
    for bar_idx in range(TARGET_ENTRY_BAR, min(pyo3_exit_bar + 2, len(pyo3_df))):
        row = pyo3_df.filter(pl.col("bar_index") == bar_idx).row(0, named=True)
        if direction == "Long":
            pyo3_sl = row.get("long_sl", None)
        else:
            pyo3_sl = row.get("short_sl", None)
        print(f"  Bar {bar_idx}: Pyo3 SL = {pyo3_sl}")


if __name__ == "__main__":
    run_lifecycle_analysis()
