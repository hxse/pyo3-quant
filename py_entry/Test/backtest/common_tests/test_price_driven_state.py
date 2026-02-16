"""价格驱动状态机测试"""

import polars as pl


class TestPriceDrivenState:
    """测试价格驱动状态机"""

    def test_price_columns_exist(self, backtest_df):
        """测试价格状态列存在"""
        required_price_cols = [
            "entry_long_price",
            "entry_short_price",
            "exit_long_price",
            "exit_short_price",
        ]

        missing_cols = [
            col for col in required_price_cols if col not in backtest_df.columns
        ]
        assert len(missing_cols) == 0, f"缺少价格列: {missing_cols}"

    def test_state_inference_logic(self, backtest_df):
        """测试状态推断逻辑（基于价格组合）"""
        # 无仓位: 所有价格列都是NaN
        no_position = backtest_df.filter(
            pl.col("entry_long_price").is_nan() & pl.col("entry_short_price").is_nan()
        )

        # 持有多头: entry_long有值，exit_long无值
        hold_long = backtest_df.filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_nan()
            & pl.col("entry_short_price").is_nan()
        )

        # 持有空头: entry_short有值，exit_short无值
        hold_short = backtest_df.filter(
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_nan()
            & pl.col("entry_long_price").is_nan()
        )

        # 离场多头: entry_long和exit_long都有值
        exit_long = backtest_df.filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
        )

        # 离场空头: entry_short和exit_short都有值
        exit_short = backtest_df.filter(
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
        )

        total_rows = len(backtest_df)


class TestFinancialSmoke:
    """资金相关轻量 smoke（公式级验证由 precision_tests 统一负责）"""

    def test_current_drawdown_non_negative(self, backtest_df):
        """只保留最小不变量：current_drawdown 必须非负。"""
        # 该断言成本低且价值高，用于快速发现异常值写入。
        assert (backtest_df["current_drawdown"] >= 0).all(), (
            "current_drawdown 应始终 >= 0"
        )


class TestDataIntegrity:
    """测试数据完整性"""

    def test_no_nan_in_required_columns(self, backtest_df, required_fixed_cols):
        """测试必需列无NaN"""
        non_price_required_cols = [
            col
            for col in required_fixed_cols
            if col
            not in [
                "entry_long_price",
                "entry_short_price",
                "exit_long_price",
                "exit_short_price",
            ]
        ]

        # 矢量化检查所有非价格必需列的空值
        null_counts = backtest_df.select(
            [pl.col(col).null_count().alias(col) for col in non_price_required_cols]
        ).row(0, named=True)

        cols_with_nulls = {
            col: count for col, count in null_counts.items() if count > 0
        }
        assert len(cols_with_nulls) == 0, f"发现空值: {cols_with_nulls}"

    def test_row_count_consistency(self, backtest_df):
        """测试行数一致性"""
        # 所有列应该有相同的行数
        row_counts = {col: len(backtest_df[col]) for col in backtest_df.columns}
        unique_counts = set(row_counts.values())

        assert len(unique_counts) == 1, f"列长度不一致: {row_counts}"
