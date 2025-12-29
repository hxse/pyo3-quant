"""
检查 Pyo3 回测结果的完整字段结构
"""

import polars as pl
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig


def inspect_pyo3_result():
    config = CommonConfig(
        bars=8000,
        seed=42,
        initial_capital=10000.0,
        commission=0.001,
        timeframe="15m",
        start_time=1735689600000,
        allow_gaps=True,
        equity_cutoff_ratio=0.20,
    )

    print("=== Pyo3 回测结果结构检查 ===\n")

    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")
    assert pyo3_adapter.result is not None

    df = pyo3_adapter.result.backtest_df

    print("DataFrame 列名:")
    for col in df.columns:
        print(f"  - {col}")

    print(f"\n总行数: {len(df)}")

    # 查看 Entry Bar 3340 附近的数据
    TARGET_BAR = 3340
    print(f"\n=== Bar {TARGET_BAR} 附近数据 ===")

    df_indexed = df.with_row_index("bar_index")

    # 选择关键列
    key_cols = [
        c
        for c in df.columns
        if any(
            x in c.lower()
            for x in [
                "entry",
                "exit",
                "sl",
                "tp",
                "tsl",
                "signal",
                "position",
                "equity",
                "pnl",
            ]
        )
    ]
    print(f"\n关键列: {key_cols[:20]}...")  # 只显示前20个

    # 显示目标 Bar 的数据
    target_rows = df_indexed.filter(
        (pl.col("bar_index") >= TARGET_BAR - 1)
        & (pl.col("bar_index") <= TARGET_BAR + 20)
    )

    # 只选择非空的列
    for row_dict in target_rows.iter_rows(named=True):
        bar_idx = row_dict["bar_index"]
        if (
            bar_idx == TARGET_BAR
            or row_dict.get("first_entry_side", 0) != 0
            or row_dict.get("exit_long_price") is not None
        ):
            print(f"\nBar {bar_idx}:")
            for k, v in row_dict.items():
                if v is not None and (
                    not isinstance(v, float) or not (v != v)
                ):  # not NaN
                    print(f"  {k}: {v}")


if __name__ == "__main__":
    inspect_pyo3_result()
