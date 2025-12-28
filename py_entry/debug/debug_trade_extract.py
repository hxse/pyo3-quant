"""
修正的交易提取和对比逻辑

问题：之前的提取函数可能没有正确处理反手情况
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


def extract_pyo3_trades_v2(pyo3_df: pl.DataFrame) -> list[dict]:
    """
    改进的 Pyo3 交易提取函数

    关键改进：
    1. 正确处理反手情况（同 Bar 有 exit 和 entry）
    2. 记录更多调试信息
    """
    if "bar_index" not in pyo3_df.columns:
        pyo3_df = pyo3_df.with_row_index("bar_index")

    trades = []
    current_long = None
    current_short = None

    for row in pyo3_df.iter_rows(named=True):
        bar = row["bar_index"]
        first_entry = row["first_entry_side"]

        entry_long_price = row.get("entry_long_price")
        entry_short_price = row.get("entry_short_price")
        exit_long_price = row.get("exit_long_price")
        exit_short_price = row.get("exit_short_price")

        # 检查离场 (先处理离场，因为反手时先离场后进场)
        if exit_long_price is not None and not np.isnan(exit_long_price):
            if current_long:
                current_long["ExitBar"] = bar
                current_long["ExitPrice"] = exit_long_price
                trades.append(current_long)
                current_long = None

        if exit_short_price is not None and not np.isnan(exit_short_price):
            if current_short:
                current_short["ExitBar"] = bar
                current_short["ExitPrice"] = exit_short_price
                trades.append(current_short)
                current_short = None

        # 检查进场 (first_entry_side 标记新进场)
        if first_entry == 1:  # 多头进场
            if entry_long_price is not None and not np.isnan(entry_long_price):
                current_long = {
                    "EntryBar": bar,
                    "Side": "Long",
                    "EntryPrice": entry_long_price,
                }
        elif first_entry == -1:  # 空头进场
            if entry_short_price is not None and not np.isnan(entry_short_price):
                current_short = {
                    "EntryBar": bar,
                    "Side": "Short",
                    "EntryPrice": entry_short_price,
                }

    return trades


def main():
    config = build_config_from_strategy("reversal_extreme", bars=500, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}, seed: {config.seed}, allow_gaps: {config.allow_gaps}")
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
    btp_trades = btp_adapter.result.stats["_trades"]

    # 提取 Pyo3 交易（使用改进版本）
    pyo3_trades = extract_pyo3_trades_v2(pyo3_df)

    print(f"\nPyo3 交易数 (改进版): {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")
    print()

    # 显示 Pyo3 所有交易的 EntryBar
    pyo3_entry_bars = [t["EntryBar"] for t in pyo3_trades]
    btp_entry_bars = btp_trades["EntryBar"].tolist()

    print(f"Pyo3 Entry Bars: {sorted(pyo3_entry_bars)}")
    print(f"BTP  Entry Bars: {sorted(btp_entry_bars)}")
    print()

    # 找出差异
    pyo3_set = set(pyo3_entry_bars)
    btp_set = set(btp_entry_bars)

    btp_only = btp_set - pyo3_set
    pyo3_only = pyo3_set - btp_set

    print(f"BTP 独有: {sorted(btp_only)}")
    print(f"Pyo3 独有: {sorted(pyo3_only)}")

    # 如果有差异，分析第一个
    if btp_only:
        first_diff = min(btp_only)
        print(f"\n=== 分析 BTP 独有的 Bar {first_diff} ===")
        bt = btp_trades[btp_trades["EntryBar"] == first_diff].iloc[0]
        print(f"BTP: EntryBar={bt['EntryBar']}, ExitBar={bt['ExitBar']}")
        print(
            f"     Size={bt['Size']}, EntryPrice={bt['EntryPrice']:.4f}, ExitPrice={bt['ExitPrice']:.4f}"
        )

        # 查看 Pyo3 在这个 Bar 的状态
        bar_df = pyo3_df.with_row_index("bar_index").filter(
            pl.col("bar_index") == first_diff
        )
        print(f"\nPyo3 at Bar {first_diff}:")
        print(
            bar_df.select(
                [
                    "first_entry_side",
                    "entry_long_price",
                    "entry_short_price",
                    "exit_long_price",
                    "exit_short_price",
                ]
            )
        )


if __name__ == "__main__":
    main()
