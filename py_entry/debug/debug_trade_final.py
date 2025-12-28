"""
最终修正版：正确处理"秒杀"场景（同 Bar 进场+离场）

秒杀场景：当 first_entry_side != 0 且同时有对应的 exit_price 时，
表示在同一根 Bar 内进场后立即触发止损/止盈离场。

这种情况下，需要在一个 Bar 内完成整个交易的记录。
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


def extract_pyo3_trades_final(pyo3_df: pl.DataFrame) -> list[dict]:
    """
    最终版 Pyo3 交易提取函数

    正确处理：
    1. 普通进场/离场
    2. 反手（同 Bar 离场+进场）
    3. 秒杀（同 Bar 进场+离场）
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

        def is_valid(val):
            return val is not None and not np.isnan(val)

        # 1. 先处理持仓离场（非秒杀的正常离场）
        if is_valid(exit_long_price) and current_long:
            current_long["ExitBar"] = bar
            current_long["ExitPrice"] = exit_long_price
            trades.append(current_long)
            current_long = None

        if is_valid(exit_short_price) and current_short:
            current_short["ExitBar"] = bar
            current_short["ExitPrice"] = exit_short_price
            trades.append(current_short)
            current_short = None

        # 2. 处理新进场
        if first_entry == 1 and is_valid(entry_long_price):
            # 多头进场
            if is_valid(exit_long_price):
                # 秒杀：同 Bar 进场+离场
                trades.append(
                    {
                        "EntryBar": bar,
                        "ExitBar": bar,
                        "Side": "Long",
                        "EntryPrice": entry_long_price,
                        "ExitPrice": exit_long_price,
                        "SecondKill": True,
                    }
                )
            else:
                # 正常进场，等待后续离场
                current_long = {
                    "EntryBar": bar,
                    "Side": "Long",
                    "EntryPrice": entry_long_price,
                }

        elif first_entry == -1 and is_valid(entry_short_price):
            # 空头进场
            if is_valid(exit_short_price):
                # 秒杀：同 Bar 进场+离场
                trades.append(
                    {
                        "EntryBar": bar,
                        "ExitBar": bar,
                        "Side": "Short",
                        "EntryPrice": entry_short_price,
                        "ExitPrice": exit_short_price,
                        "SecondKill": True,
                    }
                )
            else:
                # 正常进场
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

    # 使用最终版提取
    pyo3_trades = extract_pyo3_trades_final(pyo3_df)

    print(f"\nPyo3 交易数 (最终版): {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")

    # 统计秒杀交易
    second_kill_count = sum(1 for t in pyo3_trades if t.get("SecondKill"))
    print(f"Pyo3 秒杀交易数: {second_kill_count}")
    print()

    # 找出差异
    pyo3_entry_bars = [t["EntryBar"] for t in pyo3_trades]
    btp_entry_bars = btp_trades["EntryBar"].tolist()

    pyo3_set = set(pyo3_entry_bars)
    btp_set = set(btp_entry_bars)

    btp_only = btp_set - pyo3_set
    pyo3_only = pyo3_set - btp_set

    print(f"BTP 独有: {sorted(btp_only)}")
    print(f"Pyo3 独有: {sorted(pyo3_only)}")

    if not btp_only and not pyo3_only:
        print("\n✅ Entry Bars 完全匹配！")

        # 进一步比较 ExitBar 和价格
        print("\n=== 比较 ExitBar 和价格 ===")
        mismatches = []

        for pt in pyo3_trades:
            entry_bar = pt["EntryBar"]
            # 找 BTP 对应的交易
            bt_matches = btp_trades[btp_trades["EntryBar"] == entry_bar]
            if len(bt_matches) > 0:
                bt = bt_matches.iloc[0]

                exit_bar_diff = pt["ExitBar"] != bt["ExitBar"]
                price_diff = abs(pt["ExitPrice"] - bt["ExitPrice"]) > 0.01

                if exit_bar_diff or price_diff:
                    mismatches.append(
                        {
                            "EntryBar": entry_bar,
                            "P3_ExitBar": pt["ExitBar"],
                            "BT_ExitBar": bt["ExitBar"],
                            "P3_ExitPrice": pt["ExitPrice"],
                            "BT_ExitPrice": bt["ExitPrice"],
                            "SecondKill": pt.get("SecondKill", False),
                        }
                    )

        if mismatches:
            print(f"发现 {len(mismatches)} 个 ExitBar/ExitPrice 差异:\n")
            for m in mismatches[:10]:  # 只显示前10个
                print(
                    f"Entry {m['EntryBar']}: "
                    f"P3 Exit@{m['P3_ExitBar']} Price={m['P3_ExitPrice']:.4f} | "
                    f"BT Exit@{m['BT_ExitBar']} Price={m['BT_ExitPrice']:.4f}"
                    f"{' [秒杀]' if m['SecondKill'] else ''}"
                )
        else:
            print("✅ 所有 ExitBar 和 ExitPrice 完全匹配！")


if __name__ == "__main__":
    main()
