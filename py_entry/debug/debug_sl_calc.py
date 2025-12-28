"""
深入分析 Pyo3 vs BTP 的 SL 价格计算差异

重点关注:
1. 为什么 SL 价格不同 (80.9290 vs 80.7357)
2. 两者的 SL 计算公式是否一致
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import pandas as pd
import numpy as np

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.config import CONFIG as C


def main():
    # 配置
    config = build_config_from_strategy("reversal_extreme", bars=100, seed=42)

    print("=== 策略配置 ===")
    print(f"sl_pct: {C.sl_pct}")
    print(f"tsl_atr: {C.tsl_atr}")
    print(f"atr_period: {C.atr_period}")
    print()

    # 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None

    pyo3_df = pyo3_adapter.result.backtest_df

    # 提取 OHLCV
    base_key = f"ohlcv_{config.timeframe}"
    ohlcv_df = pyo3_adapter.runner.data_dict.source[base_key]

    # 查看 Bar 62-63 的详细数据
    # backtest_df 没有 time 列，直接用 index

    print("=== Bar 62 (Signal Bar) ===")
    print(f"close: {ohlcv_df['close'][62]:.4f}")

    # 获取 ATR
    if "atr" in pyo3_df.columns:
        atr_62 = pyo3_df["atr"][62]
        print(f"atr: {atr_62:.4f}")

    print()
    print("=== Bar 63 (Entry Bar) ===")
    print(f"open: {ohlcv_df['open'][63]:.4f}")

    # Pyo3 SL 计算
    signal_close = ohlcv_df["close"][62]

    # Pyo3 sl_pct 计算: signal_close * (1 + sl_pct) for short
    sl_pct_price = signal_close * (1 + C.sl_pct)
    print(f"\nSL 百分比计算 (for short):")
    print(
        f"  signal_close * (1 + sl_pct) = {signal_close:.4f} * (1 + {C.sl_pct}) = {sl_pct_price:.4f}"
    )

    # Pyo3 tsl_atr 计算: signal_close + atr * k for short
    if "atr" in pyo3_df.columns:
        atr_62 = pyo3_df["atr"][62]
        tsl_atr_price = signal_close + atr_62 * C.tsl_atr
        print(f"\nTSL ATR 计算 (for short):")
        print(
            f"  signal_close + atr * tsl_atr = {signal_close:.4f} + {atr_62:.4f} * {C.tsl_atr} = {tsl_atr_price:.4f}"
        )

        # 有效 SL = min(sl_pct, tsl_atr) for short
        effective_sl = min(sl_pct_price, tsl_atr_price)
        print(
            f"\n有效 SL (for short) = min({sl_pct_price:.4f}, {tsl_atr_price:.4f}) = {effective_sl:.4f}"
        )

    # 查看 Pyo3 实际输出的 SL 价格
    print("\n=== Pyo3 输出的 SL 列 ===")
    if "sl_pct_price_short" in pyo3_df.columns:
        sl_cols = [
            c for c in pyo3_df.columns if "sl_" in c.lower() and "price" in c.lower()
        ]
        print(f"SL 相关列: {sl_cols}")

        # 查看 Bar 63 的 SL 价格
        bar_63_data = pyo3_df.row(63, named=True)
        for col in sl_cols:
            val = bar_63_data.get(col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                print(f"  {col}: {val}")

    # 打印 Bar 60-70 的详细数据
    print("\n=== Bar 60-70 详细数据 ===")
    print(
        pyo3_df.select(
            [
                "first_entry_side",
                "entry_short_price",
                "exit_short_price",
                "sl_pct_price_short",
                "atr",
            ]
        )[60:70]
    )


if __name__ == "__main__":
    main()
