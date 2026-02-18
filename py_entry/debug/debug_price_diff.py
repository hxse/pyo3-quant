"""
深入分析 Pyo3 和 BTP 的价格差异
找出导致 0.945 相关性偏低的具体原因
"""

import numpy as np
import polars as pl
import pandas as pd
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
from py_entry.strategies.reversal_extreme.btp import ReversalExtremeBtp
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def run_price_analysis():
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

    print(f"=== 深入价格差异分析 (Bars={config.bars}) ===\n")

    # 1. 运行两个引擎
    print("[1/5] 运行引擎...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")
    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None
    assert pyo3_adapter.runner.data_dict is not None

    ohlcv_df = generate_ohlcv_for_backtestingpy(config)
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)
    assert btp_adapter.result is not None

    # 2. 提取交易数据
    print("[2/5] 提取交易数据...")

    # Pyo3: 从 first_entry_side 和 exit 价格提取
    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 提取 Pyo3 交易
    pyo3_trades = []

    # 找所有进场 Bar
    entry_bars = pyo3_df.filter(pl.col("first_entry_side") != 0)

    for row in entry_bars.iter_rows(named=True):
        entry_bar = row["bar_index"]
        direction = "Long" if row["first_entry_side"] == 1 else "Short"

        if direction == "Long":
            entry_price = row["entry_long_price"]
            # 找 exit
            exits = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_long_price").is_not_nan()
            )
            if len(exits) > 0:
                exit_row = exits.row(0, named=True)
                exit_bar = exit_row["bar_index"]
                exit_price = exit_row["exit_long_price"]
                pyo3_trades.append(
                    {
                        "direction": direction,
                        "entry_bar": entry_bar,
                        "exit_bar": exit_bar,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                    }
                )
        else:
            entry_price = row["entry_short_price"]
            exits = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_short_price").is_not_nan()
            )
            if len(exits) > 0:
                exit_row = exits.row(0, named=True)
                exit_bar = exit_row["bar_index"]
                exit_price = exit_row["exit_short_price"]
                pyo3_trades.append(
                    {
                        "direction": direction,
                        "entry_bar": entry_bar,
                        "exit_bar": exit_bar,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                    }
                )

    pyo3_trades_df = pd.DataFrame(pyo3_trades)
    print(f"  Pyo3 交易数: {len(pyo3_trades_df)}")

    # BTP trades
    btp_trades_raw = btp_adapter.result.stats["_trades"]
    btp_trades = []
    for _, row in btp_trades_raw.iterrows():
        btp_trades.append(
            {
                "direction": "Long" if row["Size"] > 0 else "Short",
                "entry_bar": row["EntryBar"],
                "exit_bar": row["ExitBar"],
                "entry_price": row["EntryPrice"],
                "exit_price": row["ExitPrice"],
            }
        )
    btp_trades_df = pd.DataFrame(btp_trades)
    print(f"  BTP 交易数: {len(btp_trades_df)}")

    # 3. 按 entry_bar 匹配交易
    print("\n[3/5] 匹配交易...")

    pyo3_by_entry = {int(row["entry_bar"]): row for _, row in pyo3_trades_df.iterrows()}
    btp_by_entry = {int(row["entry_bar"]): row for _, row in btp_trades_df.iterrows()}

    common_entries = set(pyo3_by_entry.keys()) & set(btp_by_entry.keys())
    only_pyo3 = set(pyo3_by_entry.keys()) - set(btp_by_entry.keys())
    only_btp = set(btp_by_entry.keys()) - set(pyo3_by_entry.keys())

    print(f"  共同进场: {len(common_entries)}")
    print(f"  仅 Pyo3: {len(only_pyo3)}")
    print(f"  仅 BTP: {len(only_btp)}")

    # 3.5 Compare ATR
    print("\n[3.5/5] 比较 ATR...")
    pyo3_atr = None
    if pyo3_adapter.runner and pyo3_adapter.runner.data_dict:
        # Pyo3 stores indicators formatted as "indicator_name" (e.g. "atr")?
        # keys are usually "ohlcv_15m", etc.
        # Indicators might be in a separate storage or added to source?
        # Check available keys in source
        print("  Pyo3 Keys:", pyo3_adapter.runner.data_dict.source.keys())
        # Try to find something looking like ATR
        # Based on config, it might be stored? Or maybe internal?
        # If not exposed, we can't compare directly.
    else:
        print("  Pyo3 Runner data not accessible.")

    # 4. 分析价格差异
    print("\n[4/5] 分析价格差异...")

    entry_diffs = []
    exit_diffs = []
    exit_bar_diffs = []
    trade_diffs = []
    direction_mismatches = 0

    for entry_bar in sorted(common_entries):
        pyo3_t = pyo3_by_entry[entry_bar]
        btp_t = btp_by_entry[entry_bar]

        if pyo3_t["direction"] != btp_t["direction"]:
            direction_mismatches += 1
            continue

        entry_diff = abs(pyo3_t["entry_price"] - btp_t["entry_price"])
        exit_diff = abs(pyo3_t["exit_price"] - btp_t["exit_price"])
        exit_bar_diff = abs(pyo3_t["exit_bar"] - btp_t["exit_bar"])

        # Calculate PnL (Pct)
        if pyo3_t["direction"] == "Long":
            pyo3_pnl = (pyo3_t["exit_price"] - pyo3_t["entry_price"]) / pyo3_t[
                "entry_price"
            ]
            btp_pnl = (btp_t["exit_price"] - btp_t["entry_price"]) / btp_t[
                "entry_price"
            ]
        else:
            pyo3_pnl = (pyo3_t["entry_price"] - pyo3_t["exit_price"]) / pyo3_t[
                "entry_price"
            ]
            btp_pnl = (btp_t["entry_price"] - btp_t["exit_price"]) / btp_t[
                "entry_price"
            ]

        pnl_diff = pyo3_pnl - btp_pnl

        entry_diffs.append(entry_diff)
        exit_diffs.append(exit_diff)
        exit_bar_diffs.append(exit_bar_diff)

        trade_diffs.append(
            {
                "entry_bar": entry_bar,
                "direction": pyo3_t["direction"],
                "pyo3_exit_bar": pyo3_t["exit_bar"],
                "btp_exit_bar": btp_t["exit_bar"],
                "pyo3_exit_price": pyo3_t["exit_price"],
                "btp_exit_price": btp_t["exit_price"],
                "exit_price_diff": exit_diff,
                "exit_bar_diff": exit_bar_diff,
                "pyo3_pnl": pyo3_pnl,
                "btp_pnl": btp_pnl,
                "pnl_diff": pnl_diff,
            }
        )

    print(f"\n=== 价格差异统计 ===")
    print(f"  方向不匹配: {direction_mismatches} 笔")
    print(f"\n  Entry Price 差异:")
    print(f"    Mean: {np.mean(entry_diffs):.6f}")
    print(f"    Max:  {np.max(entry_diffs):.6f}")
    print(f"    非零数量: {sum(1 for d in entry_diffs if d > 0.0001)}")

    print(f"\n  Exit Price 差异:")
    print(f"    Mean: {np.mean(exit_diffs):.6f}")
    print(f"    Max:  {np.max(exit_diffs):.6f}")
    print(f"    非零数量: {sum(1 for d in exit_diffs if d > 0.0001)}")

    print(f"\n  Exit Bar 差异:")
    print(f"    Mean: {np.mean(exit_bar_diffs):.2f}")
    print(f"    Max:  {np.max(exit_bar_diffs)}")
    print(f"    非零数量: {sum(1 for d in exit_bar_diffs if d > 0)}")

    # 5. 找出 PnL 差异最大的交易
    print("\n[5/5] PnL 差异最大的交易...")

    # Sort by absolute pnl_diff
    trade_diffs_sorted = sorted(
        trade_diffs, key=lambda x: abs(x["pnl_diff"]), reverse=True
    )

    print(f"\n=== PnL 差异最大的 10 笔交易 ===")
    for i, t in enumerate(trade_diffs_sorted[:10]):
        print(f"\n[{i + 1}] Entry Bar {t['entry_bar']} ({t['direction']})")
        print(
            f"    Pyo3 Exit: Bar {t['pyo3_exit_bar']}, Price {t['pyo3_exit_price']:.4f}, PnL {t['pyo3_pnl'] * 100:.2f}%"
        )
        print(
            f"    BTP  Exit: Bar {t['btp_exit_bar']}, Price {t['btp_exit_price']:.4f}, PnL {t['btp_pnl'] * 100:.2f}%"
        )
        print(f"    Exit Bar Diff: {t['exit_bar_diff']}")
        print(f"    PnL Diff: {t['pnl_diff'] * 100:.2f}%")
        print(
            f"    Entry Price Pyo3: {pyo3_by_entry[t['entry_bar']]['entry_price']:.4f}"
        )
        print(
            f"    Entry Price BTP : {btp_by_entry[t['entry_bar']]['entry_price']:.4f}"
        )

    # Analyze only ones (missed trades)
    if only_pyo3:
        print(f"\n=== 仅 Pyo3 的交易 ({len(only_pyo3)}) ===")
        for bar in sorted(only_pyo3):
            t = pyo3_by_entry[bar]
            print(
                f"  Entry {bar} ({t['direction']}): Entry {t['entry_price']:.4f}, Exit {t['exit_price']:.4f}"
            )

    if only_btp:
        print(f"\n=== 仅 BTP 的交易 ({len(only_btp)}) ===")
        for bar in sorted(only_btp):
            t = btp_by_entry[bar]
            print(
                f"  Entry {bar} ({t['direction']}): Entry {t['entry_price']:.4f}, Exit {t['exit_price']:.4f}"
            )


if __name__ == "__main__":
    run_price_analysis()
