"""
深入分析 Pyo3 和 BTP 的逐笔交易差异
找出 0.955 相关性背后的具体差异来源
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
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp


def run_deep_analysis():
    config = CommonConfig(
        bars=6000,
        seed=42,
        initial_capital=10000.0,
        commission=0.001,
        timeframe="15m",
        start_time=1735689600000,
        allow_gaps=False,
    )

    print(f"=== 深度交易分析 ===")
    print(f"bars: {config.bars}, allow_gaps: {config.allow_gaps}")

    # 1. 运行两个引擎
    print("\n[1/4] 运行引擎...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    ohlcv_df = generate_ohlcv_for_backtestingpy(config)
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    # 2. 提取 Pyo3 交易数据
    print("\n[2/4] 提取 Pyo3 交易数据...")
    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 提取每笔交易的进场/离场信息
    pyo3_trades = []

    # Long trades
    long_entries = pyo3_df.filter(pl.col("first_entry_side") == 1)
    long_exits = pyo3_df.filter(
        pl.col("exit_long_price").is_not_nan() & pl.col("entry_long_price").is_not_nan()
    )

    for row in long_entries.iter_rows(named=True):
        entry_bar = row["bar_index"]
        entry_price = row["entry_long_price"]

        # 找对应的 exit
        exit_rows = long_exits.filter(pl.col("bar_index") > entry_bar)
        if len(exit_rows) > 0:
            # 取第一个 exit
            exit_row = exit_rows.row(0, named=True)
            exit_bar = exit_row["bar_index"]
            exit_price = exit_row["exit_long_price"]
            pnl_pct = exit_row["trade_pnl_pct"]

            pyo3_trades.append(
                {
                    "direction": "Long",
                    "entry_bar": entry_bar,
                    "exit_bar": exit_bar,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                }
            )

    # Short trades
    short_entries = pyo3_df.filter(pl.col("first_entry_side") == -1)
    short_exits = pyo3_df.filter(
        pl.col("exit_short_price").is_not_nan()
        & pl.col("entry_short_price").is_not_nan()
    )

    for row in short_entries.iter_rows(named=True):
        entry_bar = row["bar_index"]
        entry_price = row["entry_short_price"]

        # 找对应的 exit
        exit_rows = short_exits.filter(pl.col("bar_index") > entry_bar)
        if len(exit_rows) > 0:
            exit_row = exit_rows.row(0, named=True)
            exit_bar = exit_row["bar_index"]
            exit_price = exit_row["exit_short_price"]
            pnl_pct = exit_row["trade_pnl_pct"]

            pyo3_trades.append(
                {
                    "direction": "Short",
                    "entry_bar": entry_bar,
                    "exit_bar": exit_bar,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                }
            )

    pyo3_trades_df = (
        pd.DataFrame(pyo3_trades).sort_values("entry_bar").reset_index(drop=True)
    )
    print(f"  Pyo3 提取交易数: {len(pyo3_trades_df)}")

    # 3. 提取 BTP 交易数据
    print("\n[3/4] 提取 BTP 交易数据...")
    btp_trades_raw = btp_adapter.result.stats["_trades"]
    btp_trades = []

    for _, row in btp_trades_raw.iterrows():
        direction = "Long" if row["Size"] > 0 else "Short"
        btp_trades.append(
            {
                "direction": direction,
                "entry_bar": row["EntryBar"],
                "exit_bar": row["ExitBar"],
                "entry_price": row["EntryPrice"],
                "exit_price": row["ExitPrice"],
                "pnl_pct": row["ReturnPct"] * 100,  # Convert to %
            }
        )

    btp_trades_df = (
        pd.DataFrame(btp_trades).sort_values("entry_bar").reset_index(drop=True)
    )
    print(f"  BTP 提取交易数: {len(btp_trades_df)}")

    # 4. 对比分析
    print("\n[4/4] 对比分析...")

    # 4.1 交易对齐
    print("\n=== 4.1 交易对齐情况 ===")
    pyo3_entry_bars = set(pyo3_trades_df["entry_bar"])
    btp_entry_bars = set(btp_trades_df["entry_bar"])

    common_bars = pyo3_entry_bars & btp_entry_bars
    only_pyo3 = pyo3_entry_bars - btp_entry_bars
    only_btp = btp_entry_bars - pyo3_entry_bars

    print(f"  共同进场 Bar: {len(common_bars)}")
    print(f"  仅 Pyo3 有: {len(only_pyo3)}")
    print(f"  仅 BTP 有: {len(only_btp)}")

    if len(only_pyo3) > 0:
        print(f"  仅 Pyo3 的 Bar (前10): {sorted(only_pyo3)[:10]}")
    if len(only_btp) > 0:
        print(f"  仅 BTP 的 Bar (前10): {sorted(only_btp)[:10]}")

    # 4.2 逐笔对比（共同进场的交易）
    print("\n=== 4.2 逐笔价格差异（前20笔共同交易） ===")

    diff_count = 0
    for i, entry_bar in enumerate(sorted(common_bars)[:20]):
        pyo3_trade = pyo3_trades_df[pyo3_trades_df["entry_bar"] == entry_bar].iloc[0]
        btp_trade = btp_trades_df[btp_trades_df["entry_bar"] == entry_bar].iloc[0]

        entry_diff = abs(pyo3_trade["entry_price"] - btp_trade["entry_price"])
        exit_diff = abs(pyo3_trade["exit_price"] - btp_trade["exit_price"])
        pnl_diff = pyo3_trade["pnl_pct"] - btp_trade["pnl_pct"]

        if entry_diff > 0.001 or exit_diff > 0.001 or abs(pnl_diff) > 0.1:
            diff_count += 1
            print(f"\n[{i + 1}] Bar {entry_bar} ({pyo3_trade['direction']})")
            print(
                f"    Entry: Pyo3={pyo3_trade['entry_price']:.4f}, BTP={btp_trade['entry_price']:.4f}, Diff={entry_diff:.6f}"
            )
            print(
                f"    Exit:  Pyo3={pyo3_trade['exit_price']:.4f}, BTP={btp_trade['exit_price']:.4f}, Diff={exit_diff:.6f}"
            )
            print(
                f"    PnL%:  Pyo3={pyo3_trade['pnl_pct']:.4f}%, BTP={btp_trade['pnl_pct']:.4f}%, Diff={pnl_diff:.4f}%"
            )
            print(
                f"    Exit Bar: Pyo3={pyo3_trade['exit_bar']}, BTP={btp_trade['exit_bar']}"
            )

    if diff_count == 0:
        print("  前20笔交易价格完全一致！")

    # 4.3 统计汇总
    print("\n=== 4.3 PnL 统计汇总 ===")

    pyo3_total_pnl = pyo3_trades_df["pnl_pct"].sum()
    btp_total_pnl = btp_trades_df["pnl_pct"].sum()

    print(f"  Pyo3 总 PnL%: {pyo3_total_pnl:.2f}%")
    print(f"  BTP 总 PnL%: {btp_total_pnl:.2f}%")
    print(f"  差异: {pyo3_total_pnl - btp_total_pnl:.2f}%")

    # 4.4 Equity 曲线对比
    print("\n=== 4.4 Equity 曲线关键点对比 ===")
    pyo3_equity = pyo3_adapter.get_equity_curve()
    btp_equity = btp_adapter.get_equity_curve()

    # 采样对比
    sample_points = [0, 1000, 2000, 3000, 4000, 5000, 5999]
    for p in sample_points:
        if p < len(pyo3_equity) and p < len(btp_equity):
            diff = pyo3_equity[p] - btp_equity[p]
            pct_diff = (diff / btp_equity[p]) * 100 if btp_equity[p] != 0 else 0
            print(
                f"  Bar {p}: Pyo3={pyo3_equity[p]:.2f}, BTP={btp_equity[p]:.2f}, Diff={diff:.2f} ({pct_diff:.2f}%)"
            )


if __name__ == "__main__":
    run_deep_analysis()
