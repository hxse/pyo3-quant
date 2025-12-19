import polars as pl
import numpy as np


def run_signal_scenario():
    # ==================== Part 9: 多周期信号生成场景测试 ====================
    print("\n" + "━" * 50)
    print("Part 9: 多周期信号生成场景测试 (实际业务场景)")
    print("━" * 50 + "\n")

    # 测试31: 模拟多周期指标对齐问题
    print("--- 测试31: 模拟小周期与大周期指标对齐 ---")
    print("场景: 1h 数据和 4h SMA 对齐，4h SMA 前导部分为 NaN\n")

    # 创建模拟数据
    small_period_sma = pl.Series(
        "sma_1h", [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
    )
    # 大周期指标前4个周期还没计算出来
    large_period_sma = pl.Series(
        "sma_4h", [np.nan, np.nan, np.nan, np.nan, 102.5, 103.5, 104.5, 105.5]
    )

    df_multi_period = pl.DataFrame(
        {"time_idx": range(8), "sma_1h": small_period_sma, "sma_4h": large_period_sma}
    )

    print("多周期数据:")
    print(df_multi_period)
    print()

    # 测试32: 错误的信号生成(不处理 NaN)
    print("--- 测试32: ❌ 错误做法 - 直接比较不处理 NaN ---")
    wrong_signal = small_period_sma < large_period_sma
    df_wrong = df_multi_period.with_columns(wrong_signal.alias("signal_wrong"))
    print(df_wrong)
    print()
    print(f"⚠️  问题: 前4行的信号都是 true！(因为 100~103 都 < NaN，NaN 被视为最大值)")
    print(f"错误触发的信号数量: {wrong_signal.sum()}")
    print()

    # 测试33: 正确的信号生成(处理 NaN)
    print("--- 测试33: ✅ 正确做法 - 过滤掉包含 NaN 的比较结果 ---")

    # 方法1: 检测 NaN 并过滤
    comparison_result = small_period_sma < large_period_sma
    left_has_nan = small_period_sma.is_nan().fill_null(False)
    right_has_nan = large_period_sma.is_nan().fill_null(False)
    has_any_nan = left_has_nan | right_has_nan

    correct_signal = comparison_result & ~has_any_nan
    df_correct = df_multi_period.with_columns(
        [
            wrong_signal.alias("signal_wrong"),
            has_any_nan.alias("has_nan"),
            correct_signal.alias("signal_correct"),
        ]
    )
    print(df_correct)
    print()
    print(f"✅ 正确的信号数量: {correct_signal.sum()}")
    print(f"说明: 只有当两个 SMA 都有效时，才进行比较")
    print()

    # 测试34: 同时处理 NaN 和 null
    print("--- 测试34: 同时处理 NaN 和 null 的情况 ---")
    sma_with_both = pl.Series(
        "sma_both", [np.nan, np.nan, None, None, 102.5, 103.5, 104.5, 105.5]
    )

    df_both = pl.DataFrame(
        {"time_idx": range(8), "sma_1h": small_period_sma, "sma_4h": sma_with_both}
    )
    print("数据 (包含 NaN 和 null):")
    print(df_both)
    print()

    # 检测特殊值
    left_has_nan_2 = small_period_sma.is_nan().fill_null(False)
    left_has_null = small_period_sma.is_null()
    right_has_nan_2 = sma_with_both.is_nan().fill_null(False)
    right_has_null = sma_with_both.is_null()

    has_special = left_has_nan_2 | left_has_null | right_has_nan_2 | right_has_null

    comparison_result_2 = small_period_sma < sma_with_both
    # 注意: 比较结果可能包含 null (因为 null 会传播)
    final_signal = comparison_result_2.fill_null(False) & ~has_special

    df_final = df_both.with_columns(
        [
            has_special.alias("has_special"),
            comparison_result_2.alias("raw_comparison"),
            final_signal.alias("final_signal"),
        ]
    )
    print(df_final)
    print()
    print("说明:")
    print("  • has_special: 标记包含 NaN 或 null 的行")
    print("  • raw_comparison: 原始比较结果(可能包含 null)")
    print("  • final_signal: 最终信号(过滤特殊值，null 填充为 false)")
    print()

    # 测试35: DataFrame 方法实现
    print("--- 测试35: 使用 DataFrame 表达式实现(更简洁) ---")
    df_expr = df_both.with_columns(
        [
            # 检测任意列是否有 NaN 或 null
            (
                pl.col("sma_1h").is_nan().fill_null(False)
                | pl.col("sma_1h").is_null()
                | pl.col("sma_4h").is_nan().fill_null(False)
                | pl.col("sma_4h").is_null()
            ).alias("has_special"),
            # 生成信号
            (
                (pl.col("sma_1h") < pl.col("sma_4h")).fill_null(False)
                & ~(
                    pl.col("sma_1h").is_nan().fill_null(False)
                    | pl.col("sma_1h").is_null()
                    | pl.col("sma_4h").is_nan().fill_null(False)
                    | pl.col("sma_4h").is_null()
                )
            ).alias("signal"),
        ]
    )
    print(df_expr)
    print()
    print("✅ 推荐模式: 在 DataFrame 中使用表达式，代码更简洁且高效")
    print()
