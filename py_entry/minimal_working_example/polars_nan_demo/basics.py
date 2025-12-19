import polars as pl
import numpy as np


def run_nan_tests():
    # ==================== Part 1: NaN 测试 ====================
    print("━" * 50)
    print("Part 1: NaN 测试")
    print("━" * 50 + "\n")

    # 创建包含 NaN 的 Series
    series_with_nan = pl.Series("with_nan", [np.nan, np.nan, np.nan])
    series_normal = pl.Series("normal", [100.0, 105.15, 110.0])

    print("Series with NaN:")
    print(series_with_nan)
    print("\nSeries normal:")
    print(series_normal)
    print()

    # 测试1: NaN 的 null_count
    print("--- 测试1: NaN 是否被算作 null ---")
    print(f"series_with_nan.null_count() = {series_with_nan.null_count()}")
    print(f"series_with_nan.is_null() = {series_with_nan.is_null()}")
    print()

    # 测试2: 正常值 < NaN
    print("--- 测试2: 正常值 < NaN ---")
    result_lt = series_normal < series_with_nan
    print(f"normal < with_nan = {result_lt}")
    print(f"true 的数量: {result_lt.sum()}")
    print()

    # 测试3: NaN < 正常值
    print("--- 测试3: NaN < 正常值 ---")
    result_lt_reverse = series_with_nan < series_normal
    print(f"with_nan < normal = {result_lt_reverse}")
    print(f"true 的数量: {result_lt_reverse.sum()}")
    print()

    # 测试4: NaN > 正常值
    print("--- 测试4: NaN > 正常值 ---")
    result_gt = series_with_nan > series_normal
    print(f"with_nan > normal = {result_gt}")
    print(f"true 的数量: {result_gt.sum()}")
    print()

    # 测试5: NaN == NaN
    print("--- 测试5: NaN == NaN ---")
    result_eq = series_with_nan == series_with_nan
    print(f"with_nan == with_nan = {result_eq}")
    print(f"true 的数量: {result_eq.sum()}")
    print()

    # 测试6: 原生 Python/NumPy 比较
    print("--- 测试6: 原生 Python/NumPy 比较 (IEEE 754 标准) ---")
    nan_val = np.nan
    normal_val = 105.15
    print(f"normal_val ({normal_val}) < NaN = {normal_val < nan_val}")
    print(f"NaN < normal_val ({normal_val}) = {nan_val < normal_val}")
    print(f"NaN > normal_val ({normal_val}) = {nan_val > normal_val}")
    print(f"NaN == NaN = {nan_val == nan_val}")
    print()

    # 测试7: 使用 fill_null 看看会怎样
    print("--- 测试7: fill_null(False) 对 NaN 的影响 ---")
    result_lt_with_fill = series_normal < series_with_nan
    print(f"比较结果(填充前): {result_lt_with_fill}")
    filled = result_lt_with_fill.fill_null(False)
    print(f"fill_null(0) 后: {filled}")
    print()


def run_null_tests():
    # ==================== Part 2: null 测试 ====================
    print("\n" + "━" * 50)
    print("Part 2: null 测试")
    print("━" * 50 + "\n")

    # 创建包含 null 的 Series
    series_with_null = pl.Series("with_null", [100.0, None, 110.0])
    series_normal2 = pl.Series("normal2", [100.0, 105.15, 110.0])

    print("Series with null:")
    print(series_with_null)
    print("\nSeries normal2:")
    print(series_normal2)
    print()

    # 测试8: null 的 null_count
    print("--- 测试8: null 是否被算作 null ---")
    print(f"series_with_null.null_count() = {series_with_null.null_count()}")
    print(f"series_with_null.is_null() = {series_with_null.is_null()}")
    print()

    # 测试9: 正常值 < null
    print("--- 测试9: 正常值 < null ---")
    result_lt_null = series_normal2 < series_with_null
    print(f"normal2 < with_null = {result_lt_null}")
    print(f"结果的 null_count: {result_lt_null.null_count()}")
    print(f"true 的数量: {result_lt_null.sum()}")
    print()

    # 测试10: null < 正常值
    print("--- 测试10: null < 正常值 ---")
    result_lt_null_reverse = series_with_null < series_normal2
    print(f"with_null < normal2 = {result_lt_null_reverse}")
    print(f"结果的 null_count: {result_lt_null_reverse.null_count()}")
    print(f"true 的数量: {result_lt_null_reverse.sum()}")
    print()

    # 测试11: null == null
    print("--- 测试11: null == null ---")
    result_eq_null = series_with_null == series_with_null
    print(f"with_null == with_null = {result_eq_null}")
    print(f"结果的 null_count: {result_eq_null.null_count()}")
    print(f"true 的数量: {result_eq_null.sum()}")
    print()

    # 测试12: fill_null 对 null 的影响
    print("--- 测试12: fill_null(False) 对 null 的影响 ---")
    result_with_null_comp = series_normal2 < series_with_null
    print(f"比较结果(填充前): {result_with_null_comp}")
    print(f"null_count: {result_with_null_comp.null_count()}")
    filled = result_with_null_comp.fill_null(False)
    print(f"fill_null(0) 后: {filled}")
    print(f"null_count: {filled.null_count()}")
    print()


def run_mixed_tests():
    # ==================== Part 3: 混合场景测试 ====================
    print("\n" + "━" * 50)
    print("Part 3: 混合场景测试 (同时包含 NaN 和 null)")
    print("━" * 50 + "\n")

    # 创建混合场景的 Series
    series_mixed = pl.Series("mixed", [100.0, np.nan, None, 110.0, np.nan, None])

    print("Series with mixed NaN and null:")
    print(series_mixed)
    print()

    # 测试13: 统计 NaN 和 null
    print("--- 测试13: is_nan() 和 is_null() 统计 ---")
    is_nan_result = series_mixed.is_nan()
    is_null_result = series_mixed.is_null()

    print(f"is_nan() = {is_nan_result}")
    print(f"is_null() = {is_null_result}")
    print(f"NaN 的数量 (is_nan().sum()): {is_nan_result.sum()}")
    print(f"null 的数量 (null_count()): {series_mixed.null_count()}")
    print()

    # 测试14: drop_nulls() 的行为
    print("--- 测试14: drop_nulls() 对 NaN 和 null 的影响 ---")
    print(f"原始 series: {series_mixed}")
    dropped = series_mixed.drop_nulls()
    print(f"drop_nulls() 后: {dropped}")
    print("⚠️  注意：drop_nulls() 只删除 null，NaN 仍然保留！")
    print()

    # 测试15: drop_nans() 的行为
    print("--- 测试15: drop_nans() 对 NaN 和 null 的影响 ---")
    print(f"原始 series: {series_mixed}")
    dropped_nans = series_mixed.drop_nans()
    print(f"drop_nans() 后: {dropped_nans}")
    print("⚠️  注意：drop_nans() 只删除 NaN，null 仍然保留！")
    print()

    # 测试16: 同时删除 NaN 和 null
    print("--- 测试16: 同时删除 NaN 和 null ---")
    print(f"原始 series: {series_mixed}")
    both_dropped = series_mixed.drop_nulls().drop_nans()
    print(f"drop_nulls().drop_nans() 后: {both_dropped}")
    print()
