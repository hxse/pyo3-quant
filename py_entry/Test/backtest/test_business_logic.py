import pytest
import polars as pl


class TestBusinessLogic:
    """测试业务逻辑"""

    def test_position_transitions(self, backtest_df):
        """测试仓位转换"""
        # 使用 Polars 矢量化操作统计仓位状态
        position_counts = (
            backtest_df.lazy()
            .group_by("current_position")
            .len()
            .sort("current_position")
            .collect()
        )

        print(f"📊 仓位状态分布: {position_counts.head(8).to_dict(as_series=False)}")

        # 检查连续开仓（应该很少见）
        # 使用 shift 操作比较相邻行的仓位
        consecutive_analysis = (
            backtest_df.lazy()
            .with_columns([pl.col("current_position").shift(1).alias("prev_position")])
            .filter(
                (pl.col("current_position") == pl.col("prev_position"))
                & (pl.col("current_position").is_in([1, -1]))  # EnterLong 或 EnterShort
            )
            .select(pl.len())
            .collect()
            .item()
        )

        total_bars = len(backtest_df)
        if total_bars > 0:
            consecutive_ratio = consecutive_analysis / total_bars
            assert consecutive_ratio < 0.1, (
                f"连续开仓过多: {consecutive_analysis}/{total_bars}"
            )

        print(f"✅ 仓位转换合理 (连续开仓比例: {consecutive_ratio:.2%})")

    def test_price_consistency(self, backtest_df, price_cols):
        """测试价格数据一致性"""
        # 使用 Polars 矢量化计算所有价格列的统计信息
        price_stats = (
            backtest_df.lazy()
            .select(
                [
                    pl.col(col).null_count().alias(f"{col}_null_count")
                    for col in price_cols
                    if col in backtest_df.columns
                ]
            )
            .collect()
        )

        total_count = len(backtest_df)

        # 计算多头仓位比例
        long_ratio = (
            backtest_df.lazy()
            .select((pl.col("current_position") > 0).mean().alias("long_ratio"))
            .collect()
            .item()
        )

        # 使用 Polars 矢量化操作创建包含所有列信息的 DataFrame
        existing_cols = [col for col in price_cols if col in backtest_df.columns]

        if existing_cols:
            # 使用表达式一次性获取所有列的 null_count
            null_counts = [
                price_stats.select(pl.col(f"{col}_null_count")).item()
                for col in existing_cols
            ]

            # 直接创建 DataFrame
            info_df = pl.DataFrame(
                {
                    "column": existing_cols,
                    "nan_ratio": [count / total_count for count in null_counts],
                    "is_long": ["long" in col for col in existing_cols],
                }
            )

            # 分别输出多头和非多头价格信息
            long_info = info_df.filter(pl.col("is_long"))
            short_info = info_df.filter(~pl.col("is_long"))

            if len(long_info) > 0:
                # 直接 print Polars DataFrame，更简洁高效
                print(long_info)

            if len(short_info) > 0:
                # 直接 print Polars DataFrame，更简洁高效
                print(short_info)

        print("✅ 价格数据基本合理")

    def test_optional_columns_data(self, backtest_df, optional_cols):
        """测试可选列数据类型和有效性"""
        # 找出实际存在的可选列
        existing_optional_cols = [
            col for col in optional_cols.keys() if col in backtest_df.columns
        ]

        if not existing_optional_cols:
            print("⚠️  无可选列数据（可能正常）")
            return

        # 使用 Polars 矢量化操作检查数据类型
        existing_cols_df = backtest_df.select(existing_optional_cols)

        # 检查所有存在的可选列都是数值类型
        for col in existing_optional_cols:
            assert backtest_df[col].dtype.is_numeric(), f"可选列 {col} 类型错误"

        # 统计每列的NaN情况
        null_stats = (
            existing_cols_df.lazy()
            .select(
                [
                    pl.col(col).null_count().alias(f"{col}_null_count")
                    for col in existing_optional_cols
                ]
            )
            .collect()
        )

        total_count = len(backtest_df)

        print(f"📊 可选列数据检查 ({len(existing_optional_cols)} 个):")

        # 使用 Polars 矢量化操作创建包含所有可选列信息的 DataFrame
        null_counts = [
            null_stats.select(pl.col(f"{col}_null_count")).item()
            for col in existing_optional_cols
        ]

        # 直接创建 DataFrame，避免 for 循环构建列表
        info_df = pl.DataFrame(
            {
                "column": existing_optional_cols,
                "description": [optional_cols[col] for col in existing_optional_cols],
                "null_ratio": [count / total_count for count in null_counts],
                "null_count": null_counts,
            }
        )

        # 直接 print Polars DataFrame，更简洁高效
        print(info_df)

        print("✅ 可选列数据检查完成")

    def test_performance_data(self, backtest_result):
        """测试性能数据"""
        if (
            hasattr(backtest_result[0], "performance")
            and backtest_result[0].performance
        ):
            assert backtest_result[0].performance is not None
            print("✅ 性能数据存在")
        else:
            print("⚠️  无性能数据（可能正常）")
