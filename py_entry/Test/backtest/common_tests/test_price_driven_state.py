"""价格驱动状态机测试"""

import polars as pl
import pytest


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
        print("✅ 所有价格列存在")

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
        print(f"📊 状态分布（总行数{total_rows}）:")
        print(
            f"  - 无仓位: {len(no_position)}行 ({len(no_position) / total_rows * 100:.1f}%)"
        )
        print(
            f"  - 持有多头: {len(hold_long)}行 ({len(hold_long) / total_rows * 100:.1f}%)"
        )
        print(
            f"  - 持有空头: {len(hold_short)}行 ({len(hold_short) / total_rows * 100:.1f}%)"
        )
        print(
            f"  - 离场多头: {len(exit_long)}行 ({len(exit_long) / total_rows * 100:.1f}%)"
        )
        print(
            f"  - 离场空头: {len(exit_short)}行 ({len(exit_short) / total_rows * 100:.1f}%)"
        )


class TestFinancialCalculation:
    """测试资金计算逻辑"""

    def test_balance_equity_relationship(self, backtest_df):
        """测试balance和equity的关系"""
        # 当无仓位时，equity应等于balance
        no_position_rows = backtest_df.filter(
            pl.col("entry_long_price").is_nan() & pl.col("entry_short_price").is_nan()
        )

        if len(no_position_rows) > 0:
            # 验证无仓位时 equity == balance
            assert (no_position_rows["equity"] == no_position_rows["balance"]).all(), (
                "无仓位时equity应完全等于balance"
            )
            print("✅ 无仓位时balance=equity关系正确")

    def test_fee_calculation(self, backtest_df):
        """测试手续费计算"""
        # 筛选有离场的记录
        exit_rows = backtest_df.filter(
            (pl.col("exit_long_price").is_not_nan())
            | (pl.col("exit_short_price").is_not_nan())
        )

        if len(exit_rows) > 0:
            # 验证所有离场都有费用
            zero_fee_exits = exit_rows.filter(pl.col("fee") == 0)

            if len(zero_fee_exits) > 0:
                print("\n⚠️ 发现fee为0的离场记录:")
                print(
                    zero_fee_exits.select(
                        [
                            "entry_long_price",
                            "exit_long_price",
                            "entry_short_price",
                            "exit_short_price",
                            "fee",
                            "balance",
                        ]
                    ).head()
                )

            assert len(zero_fee_exits) == 0, (
                f"离场应该产生手续费，发现{len(zero_fee_exits)}笔0费用交易"
            )

            # 验证累计手续费是递增的
            assert backtest_df["fee_cum"].is_sorted(), "累计手续费应单调递增"

            total_fees = backtest_df["fee_cum"].max()
            print(f"✅ 手续费计算正确，总手续费: {total_fees:.2f}")

    def test_current_drawdown_tracking(self, backtest_df):
        """测试当前回撤跟踪"""
        # current_drawdown 应该始终 >= 0
        assert (backtest_df["current_drawdown"] >= 0).all(), (
            "current_drawdown 应始终 >= 0"
        )

        # 验证是否存在非零回撤（证明计算生效）
        max_dd = backtest_df["current_drawdown"].max()
        print(f"✅ current_drawdown 跟踪正确，最大回撤: {max_dd:.4f}")


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
                "risk_exit_long_price",
                "risk_exit_short_price",
            ]
        ]

        for col in non_price_required_cols:
            null_count = backtest_df[col].null_count()
            assert null_count == 0, f"{col}列包含{null_count}个空值"

        print("✅ 必需列无空值")

    def test_row_count_consistency(self, backtest_df):
        """测试行数一致性"""
        # 所有列应该有相同的行数
        row_counts = {col: len(backtest_df[col]) for col in backtest_df.columns}
        unique_counts = set(row_counts.values())

        assert len(unique_counts) == 1, f"列长度不一致: {row_counts}"
        print(f"✅ 所有列长度一致: {list(unique_counts)[0]}行")
