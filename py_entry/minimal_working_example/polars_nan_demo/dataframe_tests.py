import polars as pl
import numpy as np


def run_dataframe_tests():
    # ==================== Part 7: DataFrame 级别测试 ====================
    print("\n" + "━" * 50)
    print("Part 7: DataFrame 级别测试")
    print("━" * 50 + "\n")

    # 测试23: DataFrame 中的 NaN 和 null
    print("--- 测试23: DataFrame 中 NaN 和 null 的统计 ---")
    df = pl.DataFrame(
        {
            "col_normal": [100.0, 105.0, 110.0, 115.0],
            "col_with_nan": [100.0, np.nan, np.nan, 115.0],
            "col_with_null": [100.0, None, 110.0, None],
            "col_mixed": [100.0, np.nan, None, 115.0],
        }
    )
    print("测试 DataFrame:")
    print(df)
    print()

    # null_count() 的不同用法
    print("null_count() 统计:")
    print(f"  • df.null_count() (每列):\n{df.null_count()}")
    print()

    # NaN 统计
    print("NaN 统计 (每列):")
    for col in df.columns:
        nan_count = df[col].is_nan().fill_null(False).sum()
        print(f"  • {col}: {nan_count} 个 NaN")
    print()

    # 测试24: DataFrame 选择包含 NaN 的行
    print("--- 测试24: 选择包含 NaN 或 null 的行 ---")
    print(f"原始 DataFrame:\n{df}")
    print()

    # 选择包含 NaN 的行
    has_nan = df.select(
        pl.any_horizontal([pl.col(c).is_nan().fill_null(False) for c in df.columns])
    ).to_series()
    df_with_has_nan = df.with_columns(has_nan.alias("has_nan"))
    print(f"标记包含 NaN 的行:\n{df_with_has_nan}")
    print()

    # 选择包含 null 的行
    has_null = df.select(
        pl.any_horizontal([pl.col(c).is_null() for c in df.columns])
    ).to_series()
    df_with_has_null = df.with_columns(has_null.alias("has_null"))
    print(f"标记包含 null 的行:\n{df_with_has_null}")
    print()

    # 测试25: DataFrame 的填充操作
    print("--- 测试25: DataFrame 同时填充 NaN 和 null ---")
    print(f"原始 DataFrame:\n{df}")
    print()

    # 所有列都填充
    df_filled = df.select(
        [pl.col(c).fill_nan(-888.0).fill_null(-999.0) for c in df.columns]
    )
    print(f"fill_nan(-888).fill_null(-999) 后:\n{df_filled}")
    print("说明: NaN → -888.0, null → -999.0")
    print()
