"""
验证 TSL 更新逻辑导致的 SL 差异

场景：交易 #1 (空头)
- 进场: Bar 63, SL = 80.9290
- 出场: Bar 65, BTP ExitPrice = 80.7357

问题：为什么 BTP 的 SL 从 80.9290 降到了 80.7357？
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import pandas as pd
import talib

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.config import CONFIG as C


def main():
    config = build_config_from_strategy("reversal_extreme", bars=100, seed=42)

    # 运行 Pyo3 获取数据
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None

    # 获取 OHLCV 数据
    base_key = f"ohlcv_{config.timeframe}"
    ohlcv_df = pyo3_adapter.runner.data_dict.source[base_key].to_pandas()

    pyo3_df = pyo3_adapter.result.backtest_df

    # BTP 使用 signal bar 的 close 作为进场信号,
    # 但是 next() 执行在 "next bar"
    # 所以 Bar 62 是信号 bar, Bar 63 是进场 bar

    print("\n=== 交易 #1 (空头) 详细分析 ===")
    print(f"进场信号 Bar: 62, close = {ohlcv_df['close'].iloc[62]:.4f}")
    print(f"进场执行 Bar: 63, open = {ohlcv_df['open'].iloc[63]:.4f}")
    print()

    # 进场 SL
    signal_close = ohlcv_df["close"].iloc[62]
    signal_atr = pyo3_df["atr"][62]
    initial_sl = signal_close * (1 + C.sl_pct)
    print(f"初始 SL = {signal_close:.4f} * (1 + {C.sl_pct}) = {initial_sl:.4f}")
    print()

    # TSL 更新模拟 (BTP 逻辑)
    print("=== BTP TSL 更新模拟 ===")

    extremum = None
    sl = initial_sl

    for bar in [63, 64, 65]:
        low = ohlcv_df["low"].iloc[bar]
        high = ohlcv_df["high"].iloc[bar]
        close = ohlcv_df["close"].iloc[bar]
        atr = pyo3_df["atr"][bar - 1]  # prev_atr

        # 更新 extremum (空头找最低点)
        if extremum is None or low < extremum:
            extremum = low

        # 计算 TSL 价格
        tsl_price = extremum + atr * C.tsl_atr

        # 更新 SL (BTP 用 min，允许向下移动)
        old_sl = sl
        sl = min(sl, tsl_price)

        print(f"Bar {bar}: low={low:.4f}, high={high:.4f}, extremum={extremum:.4f}")
        print(
            f"  prev_atr={atr:.4f}, tsl_price = {extremum:.4f} + {atr:.4f} * {C.tsl_atr} = {tsl_price:.4f}"
        )
        print(f"  SL: {old_sl:.4f} -> {sl:.4f} (change: {sl - old_sl:.4f})")

        # 检查是否触发止损
        if high > sl:
            print(f"  *** 止损触发! high {high:.4f} > SL {sl:.4f} ***")
            break
        print()

    print()
    print("=== Pyo3 TSL 逻辑对比 ===")
    print(f"Pyo3 出场价: {pyo3_df['exit_short_price'][65]:.4f}")
    print(
        f"Pyo3 tsl_atr_price_short at bar 65: {pyo3_df['tsl_atr_price_short'][65]:.4f}"
    )


if __name__ == "__main__":
    main()
