import polars as pl
import numpy as np


def run_fill_tests():
    # ==================== Part 4: 填充方法测试 ====================
    print("\n" + "━" * 50)
    print("Part 4: 填充方法测试")
    print("━" * 50 + "\n")

    # 创建混合场景的 Series (re-create for standalone run if needed, but context is better if specific)
    series_mixed = pl.Series("mixed", [100.0, np.nan, None, 110.0, np.nan, None])

    # 测试17: fill_null() 对混合数据的影响
    print("--- 测试17: fill_null() 对混合数据的影响 ---")
    print(f"原始 series: {series_mixed}")
    filled_null = series_mixed.fill_null(-999.0)
    print(f"fill_null(-999.0) 后: {filled_null}")
    print("⚠️  注意：只有 null 被填充为 -999.0，NaN 保持不变！")
    print()

    # 测试18: fill_nan() 对混合数据的影响
    print("--- 测试18: fill_nan() 对混合数据的影响 ---")
    print(f"原始 series: {series_mixed}")
    filled_nan = series_mixed.fill_nan(-888.0)
    print(f"fill_nan(-888.0) 后: {filled_nan}")
    print("⚠️  注意：只有 NaN 被填充为 -888.0，null 保持不变！")
    print()

    # 测试19: 同时填充 NaN 和 null
    print("--- 测试19: 同时填充 NaN 和 null ---")
    print(f"原始 series: {series_mixed}")
    both_filled = series_mixed.fill_nan(-888.0).fill_null(-999.0)
    print(f"fill_nan(-888.0).fill_null(-999.0) 后: {both_filled}")
    print("NaN 被填充为 -888.0，null 被填充为 -999.0")
    print()

    # 测试20: 使用 forward fill 和 backward fill
    print("--- 测试20: forward fill (向前填充) ---")
    series_for_ffill = pl.Series(
        "ffill_test", [100.0, np.nan, None, 110.0, np.nan, None, 120.0]
    )
    print(f"原始 series: {series_for_ffill}")

    # 先填充 NaN，再 forward fill null
    ffilled = series_for_ffill.fill_nan(None).forward_fill()
    print(f"fill_nan(None).forward_fill() 后: {ffilled}")
    print("说明：先将 NaN 转为 null，然后用前值填充")
    print()

    # 测试21: 使用 interpolate
    print("--- 测试21: interpolate (插值) ---")
    series_for_interp = pl.Series("interp_test", [100.0, np.nan, None, 110.0])
    print(f"原始 series: {series_for_interp}")

    # 先将 NaN 转为 null，再插值
    interpolated = series_for_interp.fill_nan(None).interpolate()
    print(f"fill_nan(None).interpolate() 后: {interpolated}")
    print("说明：先将 NaN 转为 null，然后线性插值")
    print()
