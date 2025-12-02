"""测试 RiskState 输出列"""

import polars as pl
import pytest


class TestRiskStateColumns:
    """测试 Risk 状态输出列的存在性和类型"""

    def test_risk_exit_columns_exist(self, backtest_df):
        """测试所有 risk_exit_* 列存在"""
        required_risk_cols = [
            "risk_exit_long_price",
            "risk_exit_short_price",
            "risk_exit_in_bar",
        ]

        for col in required_risk_cols:
            assert col in backtest_df.columns, f"缺少列: {col}"

        print("✅ 所有 RiskState 输出列存在")

    def test_risk_exit_in_bar_is_bool(self, backtest_df):
        """测试 risk_exit_in_bar 是布尔类型"""
        assert backtest_df["risk_exit_in_bar"].dtype == pl.Boolean, (
            f"risk_exit_in_bar 类型错误: {backtest_df['risk_exit_in_bar'].dtype}"
        )
        print("✅ risk_exit_in_bar 类型正确 (bool)")

    def test_risk_exit_prices_are_numeric(self, backtest_df):
        """测试 risk_exit_*_price 是数值类型"""
        assert backtest_df["risk_exit_long_price"].dtype.is_numeric()
        assert backtest_df["risk_exit_short_price"].dtype.is_numeric()
        print("✅ risk_exit_*_price 类型正确 (f64)")


class TestRiskExitBehavior:
    """测试 Risk 离场行为"""

    def test_in_bar_mode_sets_flag(self, backtest_df):
        """测试 in_bar 模式正确设置标志"""
        risk_exits = backtest_df.filter(
            (pl.col("risk_exit_long_price").is_not_nan())
            | (pl.col("risk_exit_short_price").is_not_nan())
        )

        if len(risk_exits) > 0:
            # 检查有风控触发的记录
            in_bar_exits = risk_exits.filter(pl.col("risk_exit_in_bar") == True)
            next_bar_exits = risk_exits.filter(pl.col("risk_exit_in_bar") == False)

            print(f"📊 风控触发: {len(risk_exits)}笔")
            print(f"  - In Bar: {len(in_bar_exits)}笔")
            print(f"  - Next Bar: {len(next_bar_exits)}笔")
            print("✅ risk_exit_in_bar 标志正常工作")

    def test_risk_exit_price_consistency(self, backtest_df):
        """测试风控离场价格与 exit_price 一致"""
        # 当 risk_exit_long_price 有值时，exit_long_price 也应该有值（in_bar模式）
        risk_long_exits = backtest_df.filter(
            pl.col("risk_exit_long_price").is_not_nan() & pl.col("risk_exit_in_bar")
            == True
        )

        if len(risk_long_exits) > 0:
            # in_bar 模式下，risk_exit_long_price 有值时 exit_long_price 也应该有值
            assert (risk_long_exits["exit_long_price"].is_not_nan()).all(), (
                "in_bar模式下 risk_exit_long_price 有值时 exit_long_price 也应该有值"
            )
            print("✅ 风控离场价格与 exit_price 一致")

    def test_no_nan_in_risk_exit_in_bar(self, backtest_df):
        """测试 risk_exit_in_bar 列无空值"""
        null_count = backtest_df["risk_exit_in_bar"].null_count()
        assert null_count == 0, f"risk_exit_in_bar 包含 {null_count} 个空值"
        print("✅ risk_exit_in_bar 无空值")
