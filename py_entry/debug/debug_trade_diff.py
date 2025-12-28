"""
深入分析交易数量差异的根本原因

Pyo3: 40 笔交易
BTP:  51 笔交易

差异: BTP 多了 11 笔

需要找出：
1. BTP 多出的交易在哪些 Bar
2. 这些交易为什么 Pyo3 没有捕获到
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


def extract_pyo3_trades(pyo3_df: pl.DataFrame) -> list[dict]:
    """从 Pyo3 结果中提取交易记录"""
    if "bar_index" not in pyo3_df.columns:
        pyo3_df = pyo3_df.with_row_index("bar_index")

    trades = []
    current_trade = None

    for row in pyo3_df.iter_rows(named=True):
        bar = row["bar_index"]

        # 检查进场
        if row["first_entry_side"] == 1:
            current_trade = {
                "EntryBar": bar,
                "Side": "Long",
                "EntryPrice": row["entry_long_price"],
            }
        elif row["first_entry_side"] == -1:
            current_trade = {
                "EntryBar": bar,
                "Side": "Short",
                "EntryPrice": row["entry_short_price"],
            }

        # 检查离场
        if current_trade:
            exit_price = None
            if (
                current_trade["Side"] == "Long"
                and row["exit_long_price"] is not None
                and not np.isnan(row["exit_long_price"])
            ):
                exit_price = row["exit_long_price"]
            elif (
                current_trade["Side"] == "Short"
                and row["exit_short_price"] is not None
                and not np.isnan(row["exit_short_price"])
            ):
                exit_price = row["exit_short_price"]

            if exit_price is not None:
                current_trade["ExitBar"] = bar
                current_trade["ExitPrice"] = exit_price
                trades.append(current_trade)
                current_trade = None

    return trades


def main():
    config = build_config_from_strategy("reversal_extreme", bars=500, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}")
    print(f"seed: {config.seed}")
    print(f"allow_gaps: {config.allow_gaps}")
    print()

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None

    pyo3_df = pyo3_adapter.result.backtest_df

    # 提取共享数据给 BTP
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
    assert btp_adapter.result.stats is not None

    btp_trades = btp_adapter.result.stats["_trades"]
    pyo3_trades = extract_pyo3_trades(pyo3_df)

    print(f"\nPyo3 交易数: {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")
    print()

    # 创建集合来找出差异
    pyo3_entry_bars = set(t["EntryBar"] for t in pyo3_trades)
    btp_entry_bars = set(btp_trades["EntryBar"].tolist())

    # BTP 有但 Pyo3 没有的交易
    btp_only = btp_entry_bars - pyo3_entry_bars
    # Pyo3 有但 BTP 没有的交易
    pyo3_only = pyo3_entry_bars - btp_entry_bars

    print(f"=== 交易差异分析 ===")
    print(f"BTP 独有的 EntryBar (共 {len(btp_only)} 个): {sorted(btp_only)}")
    print(f"Pyo3 独有的 EntryBar (共 {len(pyo3_only)} 个): {sorted(pyo3_only)}")
    print()

    # 详细分析 BTP 独有的交易
    if btp_only:
        print("=== BTP 独有交易详情 ===")
        for entry_bar in sorted(btp_only):
            bt = btp_trades[btp_trades["EntryBar"] == entry_bar].iloc[0]
            print(f"EntryBar {entry_bar}:")
            print(f"  Size: {bt['Size']}, EntryPrice: {bt['EntryPrice']:.4f}")
            print(f"  ExitBar: {bt['ExitBar']}, ExitPrice: {bt['ExitPrice']:.4f}")
            print(f"  SL: {bt['SL']:.4f}, TP: {bt['TP']:.4f}")
            print()

    # 分析第一个差异的 Bar 附近的 Pyo3 状态
    if btp_only:
        first_diff_bar = min(btp_only)
        print(f"=== 分析 Bar {first_diff_bar} 附近的 Pyo3 状态 ===")

        # 查看 first_diff_bar 附近的 Pyo3 数据
        start = max(0, first_diff_bar - 3)
        end = min(len(pyo3_df), first_diff_bar + 3)

        cols = [
            "first_entry_side",
            "entry_long_price",
            "entry_short_price",
            "exit_long_price",
            "exit_short_price",
        ]

        available_cols = [c for c in cols if c in pyo3_df.columns]
        slice_df = pyo3_df.select(available_cols)[start:end].with_row_index(
            "bar_index", offset=start
        )
        print(slice_df)

        # 查看对应的 OHLC
        print(f"\nBar {first_diff_bar} 的 OHLC:")
        row = ohlcv_df.iloc[first_diff_bar]
        print(f"  Open: {row['Open']:.4f}, High: {row['High']:.4f}")
        print(f"  Low: {row['Low']:.4f}, Close: {row['Close']:.4f}")


if __name__ == "__main__":
    main()
