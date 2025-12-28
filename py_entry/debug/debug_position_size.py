"""
深入分析仓位大小和复利效应

问题：只有 8 笔交易的 Exit 有差异，但回报率差了 80%
可能原因：
1. 仓位大小计算方式不同
2. 复利效应累积
3. Commission 计算方式不同
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
    print(f"initial_capital: {config.initial_capital}")
    print(f"commission: {config.commission}")
    print()

    # 运行引擎
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

    print("运行 BTP...")
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    assert btp_adapter.result is not None
    btp_trades = btp_adapter.result.stats["_trades"]

    # 检查 Pyo3 的 position_size 列
    print("\n=== Pyo3 仓位大小 ===")

    # 看看 pyo3_df 有哪些列
    print("Pyo3 DataFrame 列名:")
    for col in pyo3_df.columns:
        print(f"  {col}")

    # 检查第一笔交易的详细信息
    print("\n\n=== 第一笔交易 (Entry Bar 60) 详细对比 ===")

    # BTP 数据
    bt = btp_trades[btp_trades["EntryBar"] == 60].iloc[0]
    print(f"BTP:")
    print(f"  Size: {bt['Size']}")
    print(f"  EntryPrice: {bt['EntryPrice']:.4f}")
    print(f"  ExitPrice: {bt['ExitPrice']:.4f}")
    print(f"  PnL: {bt['PnL']:.4f}")
    print(f"  ReturnPct: {bt['ReturnPct']:.4f}")

    # Pyo3 数据
    pyo3_entry = pyo3_df.filter(pl.col("bar_index") == 60).row(0, named=True)
    pyo3_exit = pyo3_df.filter(
        (pl.col("bar_index") >= 60) & pl.col("exit_long_price").is_not_nan()
    ).row(0, named=True)

    print(f"\nPyo3:")
    print(f"  Entry Price: {pyo3_entry['entry_long_price']:.4f}")
    print(f"  Exit Bar: {pyo3_exit['bar_index']}")
    print(f"  Exit Price: {pyo3_exit['exit_long_price']:.4f}")

    # 检查 balance 和 equity 变化
    print(f"\nPyo3 Balance/Equity 变化:")
    for bar in [59, 60, 61, 62]:
        row = pyo3_df.filter(pl.col("bar_index") == bar).row(0, named=True)
        print(f"  Bar {bar}: balance={row['balance']:.2f}, equity={row['equity']:.2f}")

    # 计算 Pyo3 的仓位大小
    entry_bar_row = pyo3_df.filter(pl.col("bar_index") == 60).row(0, named=True)
    prev_bar_row = pyo3_df.filter(pl.col("bar_index") == 59).row(0, named=True)

    prev_balance = prev_bar_row["balance"]
    entry_price = entry_bar_row["entry_long_price"]

    # 估算仓位大小
    pyo3_size_estimate = prev_balance / entry_price
    print(f"\nPyo3 仓位估算:")
    print(f"  前一 Bar Balance: {prev_balance:.2f}")
    print(f"  Entry Price: {entry_price:.4f}")
    print(f"  估算 Size (100%资金): {pyo3_size_estimate:.2f}")
    print(f"  BTP 实际 Size: {abs(bt['Size'])}")
    print(f"  Size 差异: {pyo3_size_estimate - abs(bt['Size']):.2f}")

    # BTP 用的是 size=0.99
    from py_entry.Test.backtest.strategies.reversal_extreme.btp import size as btp_size

    print(f"\nBTP size 参数: {btp_size}")

    # 前 10 笔交易的 PnL 对比
    print("\n\n=== 前 10 笔交易 PnL 对比 ===")
    print(
        f"{'Entry':<8} {'Side':<6} {'BTP Size':<10} {'BTP PnL':<12} {'Pyo3 PnL':<12} {'Diff':<12}"
    )

    for i, (_, bt) in enumerate(btp_trades.head(10).iterrows()):
        entry_bar = bt["EntryBar"]
        is_long = bt["Size"] > 0

        # 找 Pyo3 的 exit
        if is_long:
            exits = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_long_price").is_not_nan()
            )
            exit_col = "exit_long_price"
        else:
            exits = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_short_price").is_not_nan()
            )
            exit_col = "exit_short_price"

        if len(exits) == 0:
            continue

        pyo3_exit_row = exits.row(0, named=True)

        # 查找这笔 Pyo3 交易的 PnL
        pyo3_trade_pnl = pyo3_exit_row.get("trade_pnl_pct", None)
        if pyo3_trade_pnl is not None:
            pyo3_trade_pnl = pyo3_trade_pnl * 100  # 转换为百分比
        else:
            pyo3_trade_pnl = float("nan")

        btp_return_pct = bt["ReturnPct"] * 100

        diff = (
            pyo3_trade_pnl - btp_return_pct
            if not np.isnan(pyo3_trade_pnl)
            else float("nan")
        )

        direction = "Long" if is_long else "Short"
        print(
            f"{entry_bar:<8} {direction:<6} {bt['Size']:<10} {btp_return_pct:<12.4f} {pyo3_trade_pnl:<12.4f} {diff:<12.4f}"
        )

    # 检查净值曲线差异
    print("\n\n=== 净值曲线对比 ===")
    pyo3_equity = pyo3_adapter.get_equity_curve()
    btp_equity = btp_adapter.get_equity_curve()

    print(
        f"{'Bar':<8} {'Pyo3 Equity':<15} {'BTP Equity':<15} {'Diff':<12} {'Diff %':<12}"
    )
    for bar in [0, 50, 100, 150, 200, 250, 300, 350, 400, 450, 499]:
        if bar < len(pyo3_equity) and bar < len(btp_equity):
            diff = pyo3_equity[bar] - btp_equity[bar]
            diff_pct = diff / btp_equity[bar] * 100
            print(
                f"{bar:<8} {pyo3_equity[bar]:<15.2f} {btp_equity[bar]:<15.2f} {diff:<12.2f} {diff_pct:<12.2f}"
            )


if __name__ == "__main__":
    main()
