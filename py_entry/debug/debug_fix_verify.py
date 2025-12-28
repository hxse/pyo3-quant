"""
验证修改 tsl_anchor_mode=True 是否能修复 Pyo3 和 BTP 的差异

前提：
分析发现 BTP 始终使用 Extremum (High/Low) 计算 TSL，
而 Pyo3 默认配置 tsl_anchor_mode=False (Close)。
这导致 BTP 的 TSL 总是更紧。

本脚本：
1. 使用 tsl_anchor_mode=True 覆盖配置
2. 运行 Pyo3 和 BTP (500 bars, allow_gaps=False)
3. 比较交易结果
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
from py_entry.Test.backtest.strategies import get_strategy


def extract_pyo3_trades_final(pyo3_df: pl.DataFrame) -> list[dict]:
    """复制 debug_trade_final.py 中的提取逻辑"""
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

        if first_entry == 1 and is_valid(entry_long_price):
            if is_valid(exit_long_price):
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
                current_long = {
                    "EntryBar": bar,
                    "Side": "Long",
                    "EntryPrice": entry_long_price,
                }

        elif first_entry == -1 and is_valid(entry_short_price):
            if is_valid(exit_short_price):
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
                current_short = {
                    "EntryBar": bar,
                    "Side": "Short",
                    "EntryPrice": entry_short_price,
                }

    return trades


def main():
    config = build_config_from_strategy("reversal_extreme", bars=6000, seed=42)

    # === 关键：修改策略配置 ===
    print("=== 修改配置: tsl_anchor_mode = True ===")
    strategy = get_strategy("reversal_extreme")
    strategy.engine_settings.tsl_anchor_mode = True

    # 打印确认
    print(f"Strategy tsl_anchor_mode: {strategy.engine_settings.tsl_anchor_mode}")
    print()

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

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

    btp_trades = btp_adapter.result.stats["_trades"]
    pyo3_trades = extract_pyo3_trades_final(pyo3_df)

    print(f"\nPyo3 交易数: {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")

    # 验证 Exit 匹配度
    mismatches = []

    for pt in pyo3_trades:
        entry_bar = pt["EntryBar"]
        bt_matches = btp_trades[btp_trades["EntryBar"] == entry_bar]
        if len(bt_matches) > 0:
            bt = bt_matches.iloc[0]

            # 使用更严格的判断，但允许非常小的误差
            exit_bar_diff = pt["ExitBar"] != bt["ExitBar"]
            price_diff = abs(pt["ExitPrice"] - bt["ExitPrice"]) > 0.01

            if exit_bar_diff or price_diff:
                mismatches.append(
                    {
                        "EntryBar": entry_bar,
                        "P3_Exit": (pt["ExitBar"], pt["ExitPrice"]),
                        "BT_Exit": (bt["ExitBar"], bt["ExitPrice"]),
                    }
                )

    if mismatches:
        print(f"\n❌ 仍有 {len(mismatches)} 个不匹配:")
        for m in mismatches:
            print(f"Entry {m['EntryBar']}: P3 {m['P3_Exit']} vs BT {m['BT_Exit']}")
    else:
        print("\n✅ 完美匹配！所有交易离场一致！")


if __name__ == "__main__":
    main()
