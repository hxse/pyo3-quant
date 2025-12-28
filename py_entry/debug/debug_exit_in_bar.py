"""
深入对比 Pyo3 exit_in_bar=True vs Backtesting.py 官方 SL

关键问题：为什么 exit_in_bar=True 时相关性反而更差（-0.64）？
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

from py_entry.Test.backtest.strategies.reversal_extreme import get_config
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp

import dataclasses
import pandas as pd
import numpy as np


def run_comparison(exit_in_bar: bool, num_bars: int = 500):
    """对比测试"""

    # 获取策略配置
    strategy_config = get_config()

    # 临时修改 exit_in_bar
    from py_entry.Test.backtest.strategies.reversal_extreme import (
        config as strategy_cfg,
    )

    original_exit_in_bar = strategy_cfg.CONFIG.exit_in_bar
    strategy_cfg.CONFIG = dataclasses.replace(
        strategy_cfg.CONFIG, exit_in_bar=exit_in_bar
    )

    # 设置测试配置
    config = build_config_from_strategy("reversal_extreme")
    config.bars = num_bars
    config.seed = 42

    # 运行 Pyo3
    print(f"\n=== exit_in_bar={exit_in_bar}, num_bars={num_bars} ===")
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    pyo3_equity = pyo3_adapter.get_equity_curve()
    pyo3_result = pyo3_adapter.result

    # 运行 Backtesting.py
    print("运行 Backtesting.py...")
    ohlcv_df = generate_ohlcv_for_backtestingpy(config)

    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    assert btp_adapter.result is not None
    assert btp_adapter.result.stats is not None
    btp_equity = btp_adapter.get_equity_curve()
    btp_stats = btp_adapter.result.stats

    # 恢复配置
    strategy_cfg.CONFIG = dataclasses.replace(
        strategy_cfg.CONFIG, exit_in_bar=original_exit_in_bar
    )

    # 对比结果
    print(f"\n结果对比:")
    print(f"  Pyo3 最终净值: {pyo3_equity[-1]:.2f}")
    print(f"  BTP 最终净值:  {btp_equity[-1]:.2f}")
    print(f"  Pyo3 交易数:   {pyo3_adapter.get_trade_count()}")
    print(f"  BTP 交易数:    {btp_adapter.get_trade_count()}")

    # 计算相关性
    min_len = min(len(pyo3_equity), len(btp_equity))
    corr = np.corrcoef(pyo3_equity[:min_len], btp_equity[:min_len])[0, 1]
    print(f"  相关性:        {corr:.4f}")

    # 打印前几笔交易对比
    print(f"\n=== Pyo3 前 10 笔交易 ===")
    if pyo3_result and pyo3_result.backtest_df is not None:
        df = pyo3_result.backtest_df
        # 找到有 exit 的行
        exits = df.filter(
            [
                "bar_index",
                "entry_long",
                "entry_short",
                "exit_long",
                "exit_short",
                "entry_long_price",
                "entry_short_price",
                "exit_long_price",
                "exit_short_price",
            ]
        )
        trade_rows = exits.filter(
            (exits["exit_long"] == True) | (exits["exit_short"] == True)
        ).head(10)
        print(trade_rows)

    print(f"\n=== BTP 前 10 笔交易 ===")
    btp_trades = btp_stats["_trades"]
    print(
        btp_trades[
            [
                "EntryBar",
                "ExitBar",
                "Size",
                "EntryPrice",
                "ExitPrice",
                "PnL",
                "SL",
                "TP",
            ]
        ].head(10)
    )

    return corr


def main():
    print("=" * 60)
    print("对比 exit_in_bar 对相关性的影响")
    print("=" * 60)

    corr_false = run_comparison(exit_in_bar=False, num_bars=500)
    corr_true = run_comparison(exit_in_bar=True, num_bars=500)

    print("\n" + "=" * 60)
    print("总结:")
    print(f"  exit_in_bar=False: 相关性 {corr_false:.4f}")
    print(f"  exit_in_bar=True:  相关性 {corr_true:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
