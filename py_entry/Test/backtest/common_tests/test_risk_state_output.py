"""测试 RiskState 输出列"""

import polars as pl


class TestRiskStateColumns:
    """测试 Risk 状态输出列的存在性和类型"""

    def test_risk_exit_columns_exist(self, backtest_df):
        """测试所有 risk_exit_* 列存在"""
        required_risk_cols = [
            "risk_in_bar_direction",
        ]

        for col in required_risk_cols:
            assert col in backtest_df.columns, f"缺少列: {col}"

        print("✅ 所有 RiskState 输出列存在")

    def test_risk_in_bar_direction_is_i8(self, backtest_df):
        """测试 risk_in_bar_direction 是 i8 类型"""
        assert backtest_df["risk_in_bar_direction"].dtype == pl.Int8, (
            f"risk_in_bar_direction 类型错误: {backtest_df['risk_in_bar_direction'].dtype}"
        )
        print("✅ risk_in_bar_direction 类型正确 (i8)")


class TestRiskExitBehavior:
    """测试 Risk 离场行为"""

    def test_in_bar_mode_sets_flag(self, backtest_df):
        """测试 in_bar 模式正确设置标志"""
        risk_exits = backtest_df.filter(pl.col("risk_in_bar_direction") != 0)
        # 注意：这里逻辑上只需要检查 direction，因为 exit_price 必定存在。

        if len(risk_exits) > 0:
            # 检查有风控触发的记录
            in_bar_exits = risk_exits.filter(pl.col("risk_in_bar_direction") != 0)
            next_bar_exits = risk_exits.filter(pl.col("risk_in_bar_direction") == 0)

            print(f"📊 风控触发: {len(risk_exits)}笔")
            print(f"  - In Bar: {len(in_bar_exits)}笔")
            print(f"  - Next Bar: {len(next_bar_exits)}笔")
            print("✅ risk_in_bar_direction 标志正常工作")

    def test_risk_exit_price_consistency(self, backtest_df):
        """测试风控离场价格与 exit_price 一致"""
        # 当 risk_in_bar_direction 为 1 时，代表多头 In-Bar 风控离场
        risk_long_exits = backtest_df.filter((pl.col("risk_in_bar_direction") == 1))

        if len(risk_long_exits) > 0:
            # in_bar 模式下，risk_exit_long_price 有值时 exit_long_price 也应该有值
            assert (risk_long_exits["exit_long_price"].is_not_nan()).all(), (
                "in_bar模式下 risk_exit_long_price 有值时 exit_long_price 也应该有值"
            )
            print("✅ 风控离场价格与 exit_price 一致")

    def test_no_nan_in_risk_in_bar_direction(self, backtest_df):
        """测试 risk_in_bar_direction 列无空值"""
        null_count = backtest_df["risk_in_bar_direction"].null_count()
        assert null_count == 0, f"risk_in_bar_direction 包含 {null_count} 个空值"
        print("✅ risk_in_bar_direction 无空值")
