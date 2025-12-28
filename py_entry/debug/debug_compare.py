"""
综合对比: 在相同数据下，逐笔对比 Pyo3 和 BTP 的交易
关键：找出第一个分歧点
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import pandas as pd
import numpy as np
import talib
from typing import cast, Any

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp


def main():
    # 设置配置 (直接从策略构建，可覆盖部分参数)
    config = build_config_from_strategy("reversal_extreme", bars=200, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}")
    print(f"seed: {config.seed}")
    print()

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    pyo3_result = pyo3_adapter.result
    pyo3_df = pyo3_result.backtest_df if pyo3_result else None

    # Extract Data from Pyo3 for BTP (Ensure Consistency)
    print("Extracting Data from Pyo3 for BTP...")
    if not pyo3_adapter.runner or not pyo3_adapter.runner.data_dict:
        raise RuntimeError("Pyo3 Runner failed to initialize data.")

    base_key = f"ohlcv_{config.timeframe}"
    if base_key not in pyo3_adapter.runner.data_dict.source:
        raise RuntimeError(f"Data key {base_key} not found in Pyo3 source.")

    pyo3_pl_df = pyo3_adapter.runner.data_dict.source[base_key]
    ohlcv_df = pyo3_pl_df.to_pandas()

    # Rename for Backtesting.py
    ohlcv_df = ohlcv_df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "time": "Time",
        }
    )
    # Set Index
    ohlcv_df["Time"] = pd.to_datetime(ohlcv_df["Time"], unit="ms")
    ohlcv_df = ohlcv_df.set_index("Time")

    # 运行 BTP
    print("运行 BTP...")
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    assert btp_adapter.result is not None
    assert btp_adapter.result.stats is not None

    # BTP Gap Check
    shift_close = ohlcv_df["Close"].shift(1)
    diff = (ohlcv_df["Open"] - shift_close).abs()
    gaps = diff[diff > 1e-4]
    print(f"Data Gaps: {len(gaps)}")

    # CHECK OHLC MISMATCH (Should be 0 now)
    if pyo3_adapter.runner and pyo3_adapter.runner.data_dict:
        base_key = f"ohlcv_{config.timeframe}"
        if base_key in pyo3_adapter.runner.data_dict.source:
            pyo3_source = pyo3_adapter.runner.data_dict.source[base_key]
            pyo3_open = pyo3_source["open"]

            print("\n=== OHLC Check @ 85-95 ===")
            print(f"{'Idx':<4} {'Pyo3 Open':<12} {'BTP Open':<12} {'Diff':<12}")
            for k in range(85, 96):
                p_o = pyo3_open[k]
                b_o = ohlcv_df["Open"].iloc[k]
                print(f"{k:<4} {p_o:<12.4f} {b_o:<12.4f} {p_o - b_o:<12.4f}")

    btp_trades = btp_adapter.result.stats["_trades"]

    print()
    print(f"Pyo3 交易数: {pyo3_adapter.get_trade_count()}")
    print(f"BTP 交易数: {btp_adapter.get_trade_count()}")
    print()

    # 对比前几笔交易
    print("=== BTP 前 10 笔交易 ===")
    print(
        btp_trades[
            [
                "EntryBar",
                "ExitBar",
                "Size",
                "EntryPrice",
                "ExitPrice",
                "PnL",
                "SL",
                "TP",
            ]
        ]
        .head(10)
        .to_string()
    )

    print()
    print("=== Pyo3 Exit Log ===")
    if pyo3_df is not None:
        if "bar_index" not in pyo3_df.columns:
            pyo3_df = pyo3_df.with_row_index("bar_index")

        # Re-derive exit flags from price columns if missing
        if "exit_long" not in pyo3_df.columns and "exit_long_price" in pyo3_df.columns:
            pyo3_df = pyo3_df.with_columns(
                (
                    pl.col("exit_long_price").is_not_null()
                    & pl.col("exit_long_price").is_not_nan()
                ).alias("exit_long")
            )
        if (
            "exit_short" not in pyo3_df.columns
            and "exit_short_price" in pyo3_df.columns
        ):
            pyo3_df = pyo3_df.with_columns(
                (
                    pl.col("exit_short_price").is_not_null()
                    & pl.col("exit_short_price").is_not_nan()
                ).alias("exit_short")
            )

        print("Pyo3 Exits around 88:")
        cols_88 = ["bar_index", "exit_short", "exit_short_price"]
        if "atr" in pyo3_df.columns:
            cols_88.append("atr")
        if "sl_pct_price_short" in pyo3_df.columns:
            cols_88.append("sl_pct_price_short")

        print(
            pyo3_df.filter(
                (pl.col("bar_index") >= 87) & (pl.col("bar_index") <= 90)
            ).select(cols_88)
        )

    print()
    print("=== 净值对比 ===")
    pyo3_equity = pyo3_adapter.get_equity_curve()
    btp_equity = btp_adapter.get_equity_curve()

    print(f"Bar   Pyo3净值    BTP净值     差异")
    for i in [0, 10, 20, 50, 100, 150, 199]:
        if i < len(pyo3_equity) and i < len(btp_equity):
            diff = pyo3_equity[i] - btp_equity[i]
            print(
                f"{i:3d}   {pyo3_equity[i]:10.2f}  {btp_equity[i]:10.2f}  {diff:+10.2f}"
            )

    # 找出第一个显著分歧点
    print()
    print("=== 第一个显著分歧点 ===")
    divergence_idx = -1
    for i in range(min(len(pyo3_equity), len(btp_equity))):
        diff = abs(pyo3_equity[i] - btp_equity[i])
        if diff > 100:
            print(
                f"Bar {i}: Pyo3={pyo3_equity[i]:.2f}, BTP={btp_equity[i]:.2f}, 差异={diff:.2f}"
            )
            divergence_idx = i
            break

    if divergence_idx != -1:
        # 简单分析指标
        period = 20
        std = 2.0
        close = ohlcv_df["Close"].values

        # Use cast for matype
        upper, middle, lower = talib.BBANDS(
            close, timeperiod=period, nbdevup=std, nbdevdn=std, matype=cast(Any, 0)
        )

        print(f"\nIndicators at {divergence_idx}:")
        print(f"Close: {close[divergence_idx]:.4f}")
        print(
            f"BBands: U={upper[divergence_idx]:.4f}, M={middle[divergence_idx]:.4f}, L={lower[divergence_idx]:.4f}"
        )


if __name__ == "__main__":
    main()
