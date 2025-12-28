"""
追踪 Pyo3 在 Bar 131 进场的交易的完整生命周期
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import numpy as np

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)


def main():
    config = build_config_from_strategy("reversal_extreme", bars=500, seed=42)

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 找出所有进场和离场的 Bar
    print("\n=== Pyo3 所有进场事件 ===")
    entries = pyo3_df.filter(pl.col("first_entry_side") != 0)
    print(f"总进场数: {len(entries)}")

    # 打印所有 Entry Bar
    entry_bars = entries["bar_index"].to_list()
    print(f"Entry Bars: {entry_bars}")

    print("\n=== Pyo3 所有离场事件 ===")
    exits = pyo3_df.filter(
        pl.col("exit_long_price").is_not_nan() | pl.col("exit_short_price").is_not_nan()
    )
    print(f"总离场数: {len(exits)}")

    # 打印所有 Exit Bar
    exit_bars = exits["bar_index"].to_list()
    print(f"Exit Bars: {exit_bars}")

    # 查看 Bar 131 附近的详细情况
    print("\n=== Bar 128-160 的完整状态 ===")
    cols = [
        "bar_index",
        "first_entry_side",
        "entry_short_price",
        "exit_short_price",
        "entry_long_price",
        "exit_long_price",
    ]
    slice_df = pyo3_df.filter(
        (pl.col("bar_index") >= 128) & (pl.col("bar_index") <= 160)
    ).select([c for c in cols if c in pyo3_df.columns])

    # 只显示有事件的行
    event_df = slice_df.filter(
        (pl.col("first_entry_side") != 0)
        | pl.col("exit_short_price").is_not_nan()
        | pl.col("exit_long_price").is_not_nan()
    )
    print(event_df)

    # 追踪 Bar 131 进场的交易
    print("\n=== 追踪 Bar 131 的空头交易 ===")

    # Bar 131 entry_short_price 存在，说明进场了
    entry_bar = 131

    # 查找这笔交易的离场 Bar
    # 从 Bar 131 开始找，直到 entry_short_price 变成 NaN (表示离场后重置)
    # 或者 exit_short_price 不是 NaN (表示离场)

    for i in range(entry_bar, min(entry_bar + 50, len(pyo3_df))):
        row = pyo3_df.row(i, named=True)
        entry_short = row.get("entry_short_price")
        exit_short = row.get("exit_short_price")
        first_entry = row.get("first_entry_side", 0)

        has_entry = entry_short is not None and not np.isnan(entry_short)
        has_exit = exit_short is not None and not np.isnan(exit_short)

        if has_entry or has_exit or first_entry != 0:
            print(
                f"Bar {i}: first_entry={first_entry}, "
                f"entry_short={entry_short:.4f if has_entry else 'NaN'}, "
                f"exit_short={exit_short:.4f if has_exit else 'NaN'}"
            )

        # 如果有 exit_short_price，这笔交易就结束了
        if has_exit:
            print(f"\n交易在 Bar {i} 离场，离场价格: {exit_short:.4f}")
            break

        # 如果 entry_short_price 变成 NaN（且不是刚进场），表示被清空了
        if not has_entry and i > entry_bar:
            print(f"\nBar {i}: entry_short_price 被清空，检查是否离场...")
            # 查看前一个 Bar 是否离场
            prev_row = pyo3_df.row(i - 1, named=True)
            prev_exit = prev_row.get("exit_short_price")
            if prev_exit is not None and not np.isnan(prev_exit):
                print(f"  是的，交易在 Bar {i - 1} 离场")
            else:
                print(f"  异常：entry_short_price 消失但没有 exit_short_price")
            break


if __name__ == "__main__":
    main()
