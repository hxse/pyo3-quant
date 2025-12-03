"""
demo_sma_crossover 的测试文件

测试双均线交叉策略的回测结果是否与预期输出完全一致。
"""

import polars as pl
import polars.testing as pl_testing


def test_backtest_output_matches_expected(backtest_df, expected_output):
    """
    验证回测输出与预期输出完全一致

    此测试使用黄金测试用例（Golden Test）方法：
    - 硬编码的 OHLCV 数据
    - 手动计算的预期输出
    - 零容差验证（任何差异都需要分析）
    """
    assert backtest_df is not None, "回测结果为空"
    assert expected_output is not None, "预期输出为空"

    # 检查行数是否一致
    assert backtest_df.height == expected_output.height, (
        f"行数不一致: 实际 {backtest_df.height}, 预期 {expected_output.height}"
    )

    # 检查列名是否一致
    backtest_cols = set(backtest_df.columns)
    expected_cols = set(expected_output.columns)

    missing_cols = expected_cols - backtest_cols
    extra_cols = backtest_cols - expected_cols

    assert not missing_cols, f"缺少列: {missing_cols}"
    assert not extra_cols, f"多余列: {extra_cols}"

    # 按列名排序以确保顺序一致
    sorted_cols = sorted(expected_output.columns)
    backtest_sorted = backtest_df.select(sorted_cols)
    expected_sorted = expected_output.select(sorted_cols)

    # 逐列对比
    for col in sorted_cols:
        try:
            pl_testing.assert_series_equal(
                backtest_sorted[col],
                expected_sorted[col],
                check_names=True,
                check_dtypes=True,
                abs_tol=1e-10,  # 绝对容差
                rel_tol=1e-10,  # 相对容差
            )
        except AssertionError as e:
            print(f"\n列 '{col}' 不一致:")
            print(f"实际值:\n{backtest_sorted[col]}")
            print(f"预期值:\n{expected_sorted[col]}")
            raise AssertionError(f"列 '{col}' 不一致") from e

    # 整体对比
    try:
        pl_testing.assert_frame_equal(
            backtest_sorted,
            expected_sorted,
            check_column_order=True,
            check_row_order=True,
            check_dtypes=True,
            abs_tol=1e-10,
            rel_tol=1e-10,
        )
    except AssertionError as e:
        # 如果整体对比失败，输出差异详情
        print("\n回测输出与预期不一致!")
        print("\n前10行对比:")
        print("实际输出:")
        print(backtest_sorted.head(10))
        print("\n预期输出:")
        print(expected_sorted.head(10))
        raise


def test_basic_output_structure(backtest_df):
    """
    验证回测输出的基本结构
    """
    assert backtest_df is not None, "回测结果为空"

    # 检查必需列是否存在
    required_cols = [
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
        "balance",
        "equity",
        "peak_equity",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
        "risk_exit_long_price",
        "risk_exit_short_price",
        "risk_exit_in_bar",
    ]

    for col in required_cols:
        assert col in backtest_df.columns, f"缺少必需列: {col}"

    # 检查行数
    assert backtest_df.height == 50, f"回测结果应有50行，实际 {backtest_df.height} 行"
