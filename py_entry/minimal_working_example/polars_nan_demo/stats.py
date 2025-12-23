import polars as pl
import numpy as np


def run_count_tests():
    # ==================== Part 6: NaN 计数测试 ====================
    print("\n" + "━" * 50)
    print("Part 6: NaN 计数测试 (对应 null_count)")
    print("━" * 50 + "\n")

    # 测试22: NaN 计数的不同方法
    print("--- 测试22: 统计 NaN 数量的方法 ---")
    series_for_count = pl.Series("count_test", [100.0, np.nan, None, np.nan, 110.0])
    print(f"测试 series: {series_for_count}")
    print()

    # 方法1: 直接使用 is_nan().sum()
    nan_count_1 = series_for_count.is_nan().sum()
    print(f"方法1 - is_nan().sum(): {nan_count_1}")
    print("  问题: is_nan() 对 null 返回 null，sum() 会忽略 null")
    print(f"  is_nan() 结果: {series_for_count.is_nan()}")
    print()

    # 方法2: 填充后再统计 (推荐)
    nan_count_2 = series_for_count.is_nan().fill_null(False).sum()
    print(f"方法2 - is_nan().fill_null(False).sum(): {nan_count_2}")
    print("  推荐: 更准确，显式处理了 null 位置")
    print(f"  fill_null(False) 后: {series_for_count.is_nan().fill_null(False)}")
    print()

    # 对比 null_count
    null_count = series_for_count.null_count()
    print(f"对比 - null_count(): {null_count}")
    print()

    print("总结:")
    print(f"  • NaN 数量: {nan_count_2}")
    print(f"  • null 数量: {null_count}")
    print(f"  • 总特殊值: {nan_count_2 + null_count}")
    print(f"  • 有效值: {len(series_for_count) - nan_count_2 - null_count}")
    print()


def run_edge_case_tests():
    # ==================== Part 8: 边界情况测试 ====================
    print("\n" + "━" * 50)
    print("Part 8: 边界情况测试")
    print("━" * 50 + "\n")

    # 测试26: 空 Series
    print("--- 测试26: 空 Series ---")
    empty_series = pl.Series("empty", [], dtype=pl.Float64)
    print(f"空 series: {empty_series}")
    print(f"null_count(): {empty_series.null_count()}")
    print(f"is_nan().sum(): {empty_series.is_nan().sum()}")
    print()

    # 测试27: 全 NaN
    print("--- 测试27: 全 NaN 的 Series ---")
    all_nan = pl.Series("all_nan", [np.nan, np.nan, np.nan])
    print(f"全 NaN series: {all_nan}")
    print(f"null_count(): {all_nan.null_count()}")
    print(f"NaN count: {all_nan.is_nan().fill_null(False).sum()}")
    print(f"is_nan() 结果: {all_nan.is_nan()}")
    print()

    # 测试28: 全 null
    print("--- 测试28: 全 null 的 Series ---")
    all_null = pl.Series("all_null", [None, None, None], dtype=pl.Float64)
    print(f"全 null series: {all_null}")
    print(f"null_count(): {all_null.null_count()}")
    print(f"is_nan() 结果: {all_null.is_nan()}")
    print(f"is_nan().fill_null(False): {all_null.is_nan().fill_null(False)}")
    print("说明: is_nan() 对 null 返回 null，需要 fill_null(False)")
    print()

    # 测试29: 单个元素
    print("--- 测试29: 单个元素的各种情况 ---")
    single_normal = pl.Series("single_normal", [100.0])
    single_nan = pl.Series("single_nan", [np.nan])
    single_null = pl.Series("single_null", [None], dtype=pl.Float64)

    print(f"单个正常值: {single_normal}, null_count={single_normal.null_count()}")
    print(
        f"单个 NaN: {single_nan}, null_count={single_nan.null_count()}, nan_count={single_nan.is_nan().sum()}"
    )
    print(f"单个 null: {single_null}, null_count={single_null.null_count()}")
    print()

    # 测试30: 极端长度测试
    print("--- 测试30: 交替 NaN 和 null 的模式 ---")
    alternating = pl.Series(
        "alternating",
        [np.nan if i % 2 == 0 else None for i in range(10)],
        dtype=pl.Float64,
    )
    print(f"交替模式 (前10个): {alternating}")
    nan_cnt = alternating.is_nan().fill_null(False).sum()
    null_cnt = alternating.null_count()
    print(f"NaN 数量: {nan_cnt}")
    print(f"null 数量: {null_cnt}")
    print(
        f"验证: {nan_cnt} + {null_cnt} = {nan_cnt + null_cnt} (总长度: {len(alternating)})"
    )
    print()
