import polars as pl


class TestBacktestDataQuality:
    """测试回测数据质量"""

    def test_fixed_columns_exist(self, backtest_df, required_fixed_cols, optional_cols):
        """测试固定列存在（基于output.rs源代码）"""
        # 使用 Polars 矢量化操作检查缺失列
        missing_cols = [
            col for col in required_fixed_cols if col not in backtest_df.columns
        ]

        assert len(missing_cols) == 0, f"缺少固定列: {missing_cols}"

        # 检查可选列的存在性并统计
        existing_optional_cols = [
            col for col in optional_cols.keys() if col in backtest_df.columns
        ]
        missing_optional_cols = [
            col for col in optional_cols.keys() if col not in backtest_df.columns
        ]

        print(f"✅ 所有固定列存在")
        print(
            f"📊 可选列状态: 存在 {len(existing_optional_cols)} 个，缺失 {len(missing_optional_cols)} 个"
        )
        if existing_optional_cols:
            print(f"   存在的可选列: {existing_optional_cols}")
        if missing_optional_cols:
            print(f"   缺失的可选列: {missing_optional_cols}")

    def test_data_types_correct(self, backtest_df, financial_cols, price_cols):
        """测试数据类型正确"""
        # 位置列应为数值类型
        assert backtest_df["current_position"].dtype.is_numeric(), "仓位列类型错误"

        # 使用 Polars 矢量化操作检查财务列类型
        financial_dtypes = backtest_df.select(financial_cols).dtypes
        assert all(dtype.is_numeric() for dtype in financial_dtypes), "财务列类型错误"

        # 使用 Polars 矢量化操作检查价格列类型
        price_dtypes = backtest_df.select(price_cols).dtypes
        assert all(dtype.is_numeric() for dtype in price_dtypes), "价格列类型错误"

        print("✅ 数据类型正确")

    def test_position_values_valid(self, backtest_df, valid_positions):
        """测试仓位值有效"""
        # 使用 Polars 矢量化操作检查仓位值有效性
        invalid_positions = (
            backtest_df.lazy()
            .filter(~pl.col("current_position").is_in(valid_positions))
            .select(pl.col("current_position"))
            .unique()
            .collect()
        )

        assert len(invalid_positions) == 0, f"发现无效仓位值: {invalid_positions}"

        print("✅ 仓位值有效")
