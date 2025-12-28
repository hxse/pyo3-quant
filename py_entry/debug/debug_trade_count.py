"""
深入分析交易计数差异的根本原因

核心问题：
- Pyo3 交易数: 40
- BTP 交易数: 51

需要找出为什么 BTP 认为有更多交易
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import pandas as pd
import numpy as np

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
    config = build_config_from_strategy("reversal_extreme", bars=500, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}")
    print()

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None

    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 提取共享数据
    base_key = f"ohlcv_{config.timeframe}"
    pyo3_pl_df = pyo3_adapter.runner.data_dict.source[base_key]
    ohlcv_df = pyo3_pl_df.to_pandas()

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
    ohlcv_df["Time"] = pd.to_datetime(ohlcv_df["Time"], unit="ms")
    ohlcv_df = ohlcv_df.set_index("Time")

    # 运行 BTP
    print("运行 BTP...")
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    assert btp_adapter.result is not None
    btp_trades = btp_adapter.result.stats["_trades"]

    # 分析 Pyo3 的 exit 事件
    print("\n=== Pyo3 Exit 事件统计 ===")
    long_exits = pyo3_df.filter(pl.col("exit_long_price").is_not_nan())
    short_exits = pyo3_df.filter(pl.col("exit_short_price").is_not_nan())
    print(f"Long exits: {len(long_exits)}")
    print(f"Short exits: {len(short_exits)}")
    print(f"Total exits: {len(long_exits) + len(short_exits)}")

    # 分析 Pyo3 的 first_entry_side 事件
    print("\n=== Pyo3 Entry 事件统计 ===")
    long_entries = pyo3_df.filter(pl.col("first_entry_side") == 1)
    short_entries = pyo3_df.filter(pl.col("first_entry_side") == -1)
    print(f"Long entries (first_entry_side=1): {len(long_entries)}")
    print(f"Short entries (first_entry_side=-1): {len(short_entries)}")
    print(f"Total entries: {len(long_entries) + len(short_entries)}")

    # 对比 BTP
    print("\n=== BTP 交易统计 ===")
    long_btp = btp_trades[btp_trades["Size"] > 0]
    short_btp = btp_trades[btp_trades["Size"] < 0]
    print(f"Long trades: {len(long_btp)}")
    print(f"Short trades: {len(short_btp)}")
    print(f"Total trades: {len(btp_trades)}")

    # 列出所有 Pyo3 Entry/Exit Bar
    print("\n=== Pyo3 vs BTP Entry Bars ===")

    pyo3_entry_bars = (
        pyo3_df.filter(pl.col("first_entry_side") != 0)
        .select("bar_index")
        .to_series()
        .to_list()
    )
    btp_entry_bars = btp_trades["EntryBar"].tolist()

    print(f"Pyo3 Entry Bars ({len(pyo3_entry_bars)}): {pyo3_entry_bars[:20]}...")
    print(f"BTP Entry Bars ({len(btp_entry_bars)}): {btp_entry_bars[:20]}...")

    # 找出差异
    pyo3_set = set(pyo3_entry_bars)
    btp_set = set(btp_entry_bars)

    only_btp = sorted(btp_set - pyo3_set)
    only_pyo3 = sorted(pyo3_set - btp_set)

    print(f"\nBTP 独有 Entry ({len(only_btp)}): {only_btp}")
    print(f"Pyo3 独有 Entry ({len(only_pyo3)}): {only_pyo3}")

    # 分析差异原因 - 看看 only_btp 的 bar 在 pyo3 中是什么状态
    print("\n\n=== 分析 BTP 独有 Entry 的原因 ===")
    for bar in only_btp[:5]:
        print(f"\n--- Bar {bar} ---")

        # BTP 交易信息
        bt = btp_trades[btp_trades["EntryBar"] == bar].iloc[0]
        print(
            f"BTP: Size={bt['Size']}, Entry={bt['EntryPrice']:.4f}, Exit@{bt['ExitBar']}={bt['ExitPrice']:.4f}"
        )

        # Pyo3 在该 bar 的状态
        pyo3_row = pyo3_df.filter(pl.col("bar_index") == bar).row(0, named=True)
        print(f"Pyo3 Bar {bar}: first_entry_side={pyo3_row['first_entry_side']}")
        print(f"  entry_long_price={pyo3_row['entry_long_price']}")
        print(f"  entry_short_price={pyo3_row['entry_short_price']}")
        print(f"  exit_long_price={pyo3_row['exit_long_price']}")
        print(f"  exit_short_price={pyo3_row['exit_short_price']}")

        # 看看前一个 bar
        if bar > 0:
            prev_row = pyo3_df.filter(pl.col("bar_index") == bar - 1).row(0, named=True)
            print(f"Pyo3 Bar {bar - 1} (prev):")
            print(f"  entry_short_price={prev_row['entry_short_price']}")
            print(f"  exit_short_price={prev_row['exit_short_price']}")

    # 重点分析：Pyo3 认为 Bar 131 是持仓延续，还是新交易?
    print("\n\n=== 重点分析 Bar 131 前后的持仓变化 ===")

    # 看看 Bar 106-135 的 entry_short_price 变化
    print("\nBar 106-135 的 entry_short_price 变化:")
    slice_df = pyo3_df.filter(pl.col("bar_index").is_between(106, 140))
    print(
        slice_df.select(
            ["bar_index", "first_entry_side", "entry_short_price", "exit_short_price"]
        )
    )


if __name__ == "__main__":
    main()
