import sys
from pathlib import Path
import numpy as np
import pandas as pd
import talib
import polars as pl

root_path = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()),
    None,
)
if root_path:
    sys.path.insert(0, str(root_path))

"""
MACD Signal Line 调试脚本 (更新版)
用于分析 talib 和 Rust 实现的 signal line 计算差异
- 新增: 独立计算 MACD line 和 Signal line
- 新增: 中间 EMA 值对比
- 新增: 完整差异统计
- 新增: 检查特定索引的计算过程
"""

# 添加路径
from py_entry.data_conversion.helpers.data_generator import generate_ohlcv
import pyo3_quant


def main():
    # 1. 生成测试数据
    print("=" * 80)
    print("MACD Signal Line 调试分析 (更新版)")
    print("=" * 80)

    np.random.seed(42)
    df_polars = generate_ohlcv(
        timeframe="15m", start_time=1735689600000, num_bars=100
    )  # generate_ohlcv 返回 polars DataFrame

    # 将 polars DataFrame 转换为 pandas DataFrame, 以便 talib 使用
    df_pandas = df_polars.to_pandas()
    close = df_pandas["close"].values  # 现在这里是 pandas Series, 可以使用 .values

    # 2. 参数设置
    fast_period = 12
    slow_period = 26
    signal_period = 9

    print(f"\n参数配置:")
    print(f"  Fast Period: {fast_period}")
    print(f"  Slow Period: {slow_period}")
    print(f"  Signal Period: {signal_period}")
    print(f"  数据点数: {len(close)}")

    # 3. 计算 talib MACD (完整)
    macd_talib, signal_talib, hist_talib = talib.MACD(
        close,
        fastperiod=fast_period,
        slowperiod=slow_period,
        signalperiod=signal_period,
    )

    # 3.1 独立计算 talib 的中间值
    # 计算 Fast EMA
    fast_ema_talib = talib.EMA(close, timeperiod=fast_period)
    # 计算 Slow EMA
    slow_ema_talib = talib.EMA(close, timeperiod=slow_period)
    # 计算 MACD line
    macd_line_talib = fast_ema_talib - slow_ema_talib
    # 计算 Signal line (EMA of MACD line)
    signal_independent_talib = talib.EMA(macd_line_talib, timeperiod=signal_period)

    # 4. 计算 Rust MACD
    rust_df = pyo3_quant.debug_macd(
        df_polars,  # 直接传递 polars DataFrame
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )
    macd_engine = rust_df["MACD_12_26_9"].to_numpy()
    signal_engine = rust_df["MACDs_12_26_9"].to_numpy()
    # rust_hist = rust_df["MACDh_12_26_9"].to_numpy() # hist 暂时不需要

    print("=== 前导 NaN 数量 ===")
    print(f"talib MACD: {np.sum(np.isnan(macd_talib))}")
    print(f"engine MACD: {np.sum(np.isnan(macd_engine))}")
    print(f"talib Signal: {np.sum(np.isnan(signal_talib))}")
    print(f"engine Signal: {np.sum(np.isnan(signal_engine))}")
    print(f"talib Independent Signal: {np.sum(np.isnan(signal_independent_talib))}")

    print("\n=== 第一个有效值位置 ===")
    first_valid_macd_talib = (
        np.where(~np.isnan(macd_talib))[0][0] if np.any(~np.isnan(macd_talib)) else -1
    )
    first_valid_macd_engine = (
        np.where(~np.isnan(macd_engine))[0][0] if np.any(~np.isnan(macd_engine)) else -1
    )
    first_valid_signal_talib = (
        np.where(~np.isnan(signal_talib))[0][0]
        if np.any(~np.isnan(signal_talib))
        else -1
    )
    first_valid_signal_engine = (
        np.where(~np.isnan(signal_engine))[0][0]
        if np.any(~np.isnan(signal_engine))
        else -1
    )
    first_valid_signal_indep = (
        np.where(~np.isnan(signal_independent_talib))[0][0]
        if np.any(~np.isnan(signal_independent_talib))
        else -1
    )

    print(f"talib MACD 第一个有效值在索引: {first_valid_macd_talib}")
    print(f"engine MACD 第一个有效值在索引: {first_valid_macd_engine}")
    print(f"talib Signal 第一个有效值在索引: {first_valid_signal_talib}")
    print(f"engine Signal 第一个有效值在索引: {first_valid_signal_engine}")
    print(f"talib Independent Signal 第一个有效值在索引: {first_valid_signal_indep}")

    print("\n=== Signal 初始值对比 ===")
    if first_valid_signal_talib >= 0:
        print(
            f"talib signal[{first_valid_signal_talib}]: {signal_talib[first_valid_signal_talib]}"
        )
    if first_valid_signal_engine >= 0:
        print(
            f"engine signal[{first_valid_signal_engine}]: {signal_engine[first_valid_signal_engine]}"
        )
    if first_valid_signal_indep >= 0:
        print(
            f"talib independent signal[{first_valid_signal_indep}]: {signal_independent_talib[first_valid_signal_indep]}"
        )

    # 计算 Signal 的 SMA 初始值(应该基于 MACD 的前 signal_period 个有效值)
    if first_valid_macd_talib >= 0:
        macd_for_sma = macd_line_talib[
            first_valid_macd_talib : first_valid_macd_talib + signal_period
        ]
        sma_expected = np.mean(macd_for_sma)
        print(f"\nSignal SMA 初始值(预期,基于 talib MACD line): {sma_expected}")
        if first_valid_signal_talib >= 0:
            print(
                f"差异: talib vs 预期 = {signal_talib[first_valid_signal_talib] - sma_expected}"
            )
        if first_valid_signal_indep >= 0:
            print(
                f"差异: talib independent vs 预期 = {signal_independent_talib[first_valid_signal_indep] - sma_expected}"
            )
        if first_valid_signal_engine >= 0:
            print(
                f"差异: engine vs 预期 = {signal_engine[first_valid_signal_engine] - sma_expected}"
            )

    print("\n=== 前10个有效 Fast EMA 值对比 ===")
    fast_ema_valid_talib = fast_ema_talib[~np.isnan(fast_ema_talib)][:10]
    # 注意: Rust 中可能没有直接暴露 fast_ema, 需要根据需要添加; 这里暂略

    print("\n=== 前10个有效 MACD 值对比 ===")
    macd_valid_talib = macd_talib[~np.isnan(macd_talib)][:10]
    macd_valid_engine = macd_engine[~np.isnan(macd_engine)][:10]
    for i in range(min(10, len(macd_valid_talib))):
        diff = macd_valid_engine[i] - macd_valid_talib[i]
        print(
            f"[{i}] talib: {macd_valid_talib[i]:.6f}, engine: {macd_valid_engine[i]:.6f}, diff: {diff:.6f}"
        )

    print("\n=== 前10个有效 Signal 值对比 (talib MACD vs engine) ===")
    signal_valid_talib = signal_talib[~np.isnan(signal_talib)][:10]
    signal_valid_engine = signal_engine[~np.isnan(signal_engine)][:10]
    for i in range(min(10, len(signal_valid_talib))):
        diff = signal_valid_engine[i] - signal_valid_talib[i]
        print(
            f"[{i}] talib: {signal_valid_talib[i]:.6f}, engine: {signal_valid_engine[i]:.6f}, diff: {diff:.6f}"
        )

    print(
        "\n=== 前10个有效 Independent Signal 值对比 (talib independent vs engine) ==="
    )
    signal_valid_indep = signal_independent_talib[~np.isnan(signal_independent_talib)][
        :10
    ]
    for i in range(min(10, len(signal_valid_indep))):
        diff = signal_valid_engine[i] - signal_valid_indep[i]
        print(
            f"[{i}] indep: {signal_valid_indep[i]:.6f}, engine: {signal_valid_engine[i]:.6f}, diff: {diff:.6f}"
        )

    print("\n=== 完整 Signal 差异统计 ===")
    valid_mask = ~np.isnan(signal_talib) & ~np.isnan(signal_engine)
    diffs = signal_engine[valid_mask] - signal_talib[valid_mask]
    print(f"最大绝对差异: {np.max(np.abs(diffs)) if len(diffs) > 0 else 'N/A'}")
    print(f"平均绝对差异: {np.mean(np.abs(diffs)) if len(diffs) > 0 else 'N/A'}")
    print(
        f"差异不为零的位置数: {np.sum(np.abs(diffs) > 1e-6) if len(diffs) > 0 else 'N/A'}"
    )

    # 检查特定索引 (例如第一个有效 Signal 后的计算)
    if first_valid_signal_talib >= 0 and first_valid_signal_talib + 1 < len(
        signal_talib
    ):
        idx = first_valid_signal_talib + 1
        prev_signal = signal_talib[idx - 1]
        current_macd = macd_line_talib[idx]
        alpha = 2.0 / (signal_period + 1)
        expected_next = (current_macd - prev_signal) * alpha + prev_signal
        print(f"\n=== talib Signal 第二个值手动计算验证 ===")
        print(f"前一个 Signal: {prev_signal}")
        print(f"当前 MACD: {current_macd}")
        print(f"预期下一个 Signal: {expected_next}")
        print(f"实际 talib Signal: {signal_talib[idx]}")
        print(f"差异: {signal_talib[idx] - expected_next}")

    if first_valid_signal_engine >= 0 and first_valid_signal_engine + 1 < len(
        signal_engine
    ):
        idx = first_valid_signal_engine + 1
        prev_signal = signal_engine[idx - 1]
        current_macd = macd_engine[idx]  # 假设 macd_engine 与 talib 对齐
        alpha = 2.0 / (signal_period + 1)
        expected_next = (current_macd - prev_signal) * alpha + prev_signal
        print(f"\n=== engine Signal 第二个值手动计算验证 ===")
        print(f"前一个 Signal: {prev_signal}")
        print(f"当前 MACD: {current_macd}")
        print(f"预期下一个 Signal: {expected_next}")
        print(f"实际 engine Signal: {signal_engine[idx]}")
        print(f"差异: {signal_engine[idx] - expected_next}")


if __name__ == "__main__":
    main()
