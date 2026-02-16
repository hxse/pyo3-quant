"""测试 RiskState 输出列"""

import polars as pl


class TestRiskStateColumns:
    """测试 Risk 状态输出列的存在性和类型"""

    def test_risk_exit_columns_exist(self, backtest_df):
        """测试风险方向列存在"""
        required_risk_cols = {"risk_in_bar_direction"}

        existing_cols = set(backtest_df.columns)
        missing_cols = required_risk_cols - existing_cols

        assert len(missing_cols) == 0, f"缺少列: {missing_cols}"

    def test_risk_in_bar_direction_is_i8(self, backtest_df):
        """测试 risk_in_bar_direction 是 i8 类型"""
        assert backtest_df["risk_in_bar_direction"].dtype == pl.Int8, (
            f"risk_in_bar_direction 类型错误: {backtest_df['risk_in_bar_direction'].dtype}"
        )


class TestRiskExitBehavior:
    """测试 Risk 离场行为（轻量 smoke，细节由 precision_tests 覆盖）"""

    def test_no_nan_in_risk_in_bar_direction(self, backtest_df):
        """测试 risk_in_bar_direction 列无空值"""
        null_count = backtest_df["risk_in_bar_direction"].null_count()
        assert null_count == 0, f"risk_in_bar_direction 包含 {null_count} 个空值"
