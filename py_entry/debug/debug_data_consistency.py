"""
严格验证 Pyo3 和 BTP 使用的数据是否完全一致

这是一个关键的前置检查：
1. 两个引擎必须使用完全相同的 OHLCV 数据
2. 如果数据不一致，说明配置传递有问题
3. 数据不一致时应该立即报错，而不是继续运行
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import pandas as pd
import numpy as np

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)


def verify_data_consistency(
    pyo3_df: pl.DataFrame, btp_df: pd.DataFrame, tolerance: float = 1e-10
) -> tuple[bool, list[str]]:
    """
    验证两个数据源的 OHLCV 是否完全一致

    Args:
        pyo3_df: Pyo3 的 OHLCV 数据 (Polars)
        btp_df: BTP 的 OHLCV 数据 (Pandas)
        tolerance: 容差阈值

    Returns:
        (是否一致, 错误信息列表)
    """
    errors = []

    # 1. 检查行数
    if len(pyo3_df) != len(btp_df):
        errors.append(f"行数不一致: Pyo3={len(pyo3_df)}, BTP={len(btp_df)}")
        return False, errors

    # 2. 逐列比较 OHLCV
    columns_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }

    for pyo3_col, btp_col in columns_map.items():
        pyo3_values = pyo3_df[pyo3_col].to_numpy()
        btp_values = btp_df[btp_col].values

        # 检查是否有差异
        diff = np.abs(pyo3_values - btp_values)
        max_diff = np.max(diff)

        if max_diff > tolerance:
            # 找出第一个不一致的位置
            first_diff_idx = np.argmax(diff > tolerance)
            errors.append(
                f"{btp_col} 列不一致:\n"
                f"  最大差异: {max_diff:.10f}\n"
                f"  第一个差异位置: Bar {first_diff_idx}\n"
                f"    Pyo3[{first_diff_idx}] = {pyo3_values[first_diff_idx]:.10f}\n"
                f"    BTP[{first_diff_idx}]  = {btp_values[first_diff_idx]:.10f}\n"
                f"    Diff = {diff[first_diff_idx]:.10f}"
            )

    # 3. 检查跳空一致性 (允许第一个 bar 跳空，因为没有前值)
    pyo3_close = pyo3_df["close"].to_numpy()
    pyo3_open = pyo3_df["open"].to_numpy()

    pyo3_gaps = np.abs(pyo3_open[1:] - pyo3_close[:-1])
    pyo3_gap_count = np.sum(pyo3_gaps > 1e-10)

    btp_close = btp_df["Close"].values
    btp_open = btp_df["Open"].values

    btp_gaps = np.abs(btp_open[1:] - btp_close[:-1])
    btp_gap_count = np.sum(btp_gaps > 1e-10)

    if pyo3_gap_count != btp_gap_count:
        errors.append(
            f"跳空数量不一致:\n"
            f"  Pyo3 跳空数: {pyo3_gap_count}\n"
            f"  BTP  跳空数: {btp_gap_count}"
        )

    return len(errors) == 0, errors


def main():
    # 测试多种配置
    test_configs = [
        {"bars": 100, "seed": 42, "strategy": "reversal_extreme"},
        {"bars": 500, "seed": 42, "strategy": "reversal_extreme"},
        {"bars": 1000, "seed": 123, "strategy": "reversal_extreme"},
    ]

    all_passed = True

    for test_cfg in test_configs:
        print(f"\n{'=' * 80}")
        print(f"测试配置: bars={test_cfg['bars']}, seed={test_cfg['seed']}")
        print(f"{'=' * 80}")

        config = build_config_from_strategy(
            str(test_cfg["strategy"]), bars=test_cfg["bars"], seed=test_cfg["seed"]
        )

        print(f"CommonConfig.allow_gaps: {config.allow_gaps}")

        # 1. 运行 Pyo3
        print("\n运行 Pyo3...")
        pyo3_adapter = Pyo3Adapter(config)
        pyo3_adapter.run(str(test_cfg["strategy"]))

        assert pyo3_adapter.runner is not None
        assert pyo3_adapter.runner.data_dict is not None

        # 获取 Pyo3 的 OHLCV
        base_key = f"ohlcv_{config.timeframe}"
        pyo3_ohlcv = pyo3_adapter.runner.data_dict.source[base_key]

        # 2. 生成 BTP 数据（应该使用相同的 config）
        print("生成 BTP 数据...")
        btp_ohlcv = generate_ohlcv_for_backtestingpy(config)

        # 3. 验证数据一致性
        print("\n验证数据一致性...")
        is_consistent, errors = verify_data_consistency(pyo3_ohlcv, btp_ohlcv)

        if is_consistent:
            print("✅ 数据完全一致！")
        else:
            print("❌ 数据不一致！")
            for error in errors:
                print(f"\n{error}")
            all_passed = False

            # 打印前几行数据进行对比
            print("\n前 5 行数据对比:")
            print("\nPyo3 (前5行):")
            print(pyo3_ohlcv.select(["open", "high", "low", "close"]).head(5))
            print("\nBTP (前5行):")
            print(btp_ohlcv[["Open", "High", "Low", "Close"]].head(5))

    print(f"\n{'=' * 80}")
    if all_passed:
        print("✅ 所有测试通过！数据一致性验证成功！")
    else:
        print("❌ 存在数据不一致！必须先修复配置传递问题！")
        sys.exit(1)


if __name__ == "__main__":
    main()
