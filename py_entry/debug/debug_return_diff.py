"""
深入分析回报率差异的根本原因

测试结果:
  pyo3 总回报率: 35.6171%
  btp 总回报率: 116.1868%
  总回报率差异: 80.5697%

即使交易信号完全一致，为什么回报率差这么多?
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
from py_entry.Test.backtest.strategies.reversal_extreme.config import CONFIG as C


def main():
    config = build_config_from_strategy("reversal_extreme", bars=8000, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}")
    print(f"seed: {config.seed}")
    print(f"initial_capital: {config.initial_capital}")
    print(f"commission: {config.commission}")
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

    # 基本统计
    print("\n=== 基本统计 ===")
    pyo3_equity = pyo3_adapter.get_equity_curve()
    btp_equity = btp_adapter.get_equity_curve()

    print(f"Pyo3 最终净值: {pyo3_equity[-1]:.2f}")
    print(f"BTP 最终净值: {btp_equity[-1]:.2f}")
    print(f"Pyo3 总回报率: {pyo3_adapter.get_total_return_pct():.4f}%")
    print(f"BTP 总回报率: {btp_adapter.get_total_return_pct():.4f}%")

    # 交易数量
    pyo3_trade_count = pyo3_adapter.get_trade_count()
    btp_trade_count = btp_adapter.get_trade_count()
    print(f"\nPyo3 交易数: {pyo3_trade_count}")
    print(f"BTP 交易数: {btp_trade_count}")

    # 分析 Entry Bars 差异
    pyo3_entry_bars = (
        pyo3_df.filter(pl.col("first_entry_side") != 0)
        .select("bar_index")
        .to_series()
        .to_list()
    )
    btp_entry_bars = btp_trades["EntryBar"].tolist()

    pyo3_set = set(pyo3_entry_bars)
    btp_set = set(btp_entry_bars)

    only_btp = sorted(btp_set - pyo3_set)
    only_pyo3 = sorted(pyo3_set - btp_set)

    print(f"\nEntry Bars 差异:")
    print(f"  Pyo3 Entry Bars: {len(pyo3_entry_bars)}")
    print(f"  BTP Entry Bars: {len(btp_entry_bars)}")
    print(f"  BTP 独有: {len(only_btp)}")
    print(f"  Pyo3 独有: {len(only_pyo3)}")

    # 分析 PnL 差异（在相同的 Entry Bars 上）
    print("\n\n=== 分析 PnL 差异 ===")

    common_bars = sorted(pyo3_set & btp_set)
    print(f"共同 Entry Bars 数量: {len(common_bars)}")

    # 对于每个共同的 Entry Bar，比较 Pyo3 和 BTP 的 PnL
    pnl_diffs = []
    exit_bar_diffs = []

    for entry_bar in common_bars[:50]:  # 只看前 50 笔
        # BTP 数据
        bt = btp_trades[btp_trades["EntryBar"] == entry_bar]
        if len(bt) == 0:
            continue
        bt = bt.iloc[0]
        btp_exit_bar = bt["ExitBar"]
        btp_pnl = bt["PnL"]
        btp_entry_price = bt["EntryPrice"]
        btp_exit_price = bt["ExitPrice"]
        btp_size = bt["Size"]
        is_long = btp_size > 0

        # Pyo3 数据 - 找到对应的 exit
        if is_long:
            exit_rows = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_long_price").is_not_nan()
            )
        else:
            exit_rows = pyo3_df.filter(
                (pl.col("bar_index") >= entry_bar)
                & pl.col("exit_short_price").is_not_nan()
            )

        if len(exit_rows) == 0:
            continue

        pyo3_exit_row = exit_rows.row(0, named=True)
        pyo3_exit_bar = pyo3_exit_row["bar_index"]
        pyo3_exit_price = (
            pyo3_exit_row["exit_long_price"]
            if is_long
            else pyo3_exit_row["exit_short_price"]
        )

        # Pyo3 Entry Price
        entry_row = pyo3_df.filter(pl.col("bar_index") == entry_bar).row(0, named=True)
        pyo3_entry_price = (
            entry_row["entry_long_price"] if is_long else entry_row["entry_short_price"]
        )

        # 计算 Pyo3 PnL (简化计算)
        if is_long:
            pyo3_pnl_pct = (pyo3_exit_price - pyo3_entry_price) / pyo3_entry_price
        else:
            pyo3_pnl_pct = (pyo3_entry_price - pyo3_exit_price) / pyo3_entry_price

        # 差异
        exit_diff = pyo3_exit_bar - btp_exit_bar

        if exit_diff != 0 or abs(pyo3_exit_price - btp_exit_price) > 0.01:
            pnl_diffs.append(
                {
                    "entry_bar": entry_bar,
                    "is_long": is_long,
                    "pyo3_exit_bar": pyo3_exit_bar,
                    "btp_exit_bar": btp_exit_bar,
                    "exit_bar_diff": exit_diff,
                    "pyo3_entry": pyo3_entry_price,
                    "btp_entry": btp_entry_price,
                    "pyo3_exit": pyo3_exit_price,
                    "btp_exit": btp_exit_price,
                    "price_diff": pyo3_exit_price - btp_exit_price,
                    "btp_pnl": btp_pnl,
                }
            )

    print(f"\n发现 {len(pnl_diffs)} 笔 Exit Bar 或 Exit Price 有差异的交易:")
    for d in pnl_diffs[:20]:
        direction = "Long" if d["is_long"] else "Short"
        print(f"\n  Entry {d['entry_bar']} ({direction}):")
        print(
            f"    Pyo3 Exit Bar: {d['pyo3_exit_bar']}, BTP Exit Bar: {d['btp_exit_bar']} (diff: {d['exit_bar_diff']})"
        )
        print(f"    Pyo3 Entry: {d['pyo3_entry']:.4f}, BTP Entry: {d['btp_entry']:.4f}")
        print(
            f"    Pyo3 Exit: {d['pyo3_exit']:.4f}, BTP Exit: {d['btp_exit']:.4f} (diff: {d['price_diff']:.4f})"
        )
        print(f"    BTP PnL: {d['btp_pnl']:.2f}")

    # 统计 Exit Bar 差异情况
    print("\n\n=== Exit Bar 差异统计 ===")
    exit_earlier = sum(1 for d in pnl_diffs if d["exit_bar_diff"] < 0)
    exit_later = sum(1 for d in pnl_diffs if d["exit_bar_diff"] > 0)
    exit_same = sum(1 for d in pnl_diffs if d["exit_bar_diff"] == 0)
    print(f"  Pyo3 比 BTP 早 exit: {exit_earlier}")
    print(f"  Pyo3 比 BTP 晚 exit: {exit_later}")
    print(f"  相同 exit bar (但价格差): {exit_same}")


if __name__ == "__main__":
    main()
