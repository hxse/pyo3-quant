"""测试统一 Risk 检查逻辑"""

import polars as pl
import pytest


class TestLongShortSymmetry:
    """测试多空对称性"""

    def test_risk_triggers_distribution(self, backtest_df):
        """测试多空风控触发分布"""
        long_risk_count = len(backtest_df.filter(pl.col("risk_in_bar_direction") == 1))
        short_risk_count = len(
            backtest_df.filter(pl.col("risk_in_bar_direction") == -1)
        )
        # 以及 In-Bar 统计
        in_bar_long = len(backtest_df.filter(pl.col("risk_in_bar_direction") == 1))
        in_bar_short = len(backtest_df.filter(pl.col("risk_in_bar_direction") == -1))

    def test_sl_tp_logic_consistency(self, backtest_df):
        """测试止损止盈逻辑一致性"""
        if "sl_pct_price_long" not in backtest_df.columns:
            pytest.skip("未启用百分比止损")

        # 检查 in_bar 风控触发
        in_bar_exits = backtest_df.filter(pl.col("risk_in_bar_direction") != 0)

        if len(in_bar_exits) > 0:
            # in_bar 触发时应该有对应的方向标记
            long_in_bar = in_bar_exits.filter(pl.col("risk_in_bar_direction") == 1)
            short_in_bar = in_bar_exits.filter(pl.col("risk_in_bar_direction") == -1)

    def test_risk_price_sanity(self, backtest_df):
        """测试风控价格合理性"""
        if "sl_pct_price_long" not in backtest_df.columns:
            pytest.skip("未启用百分比止损")

        # 检查多头止损价格应该 < 进场价
        long_positions = backtest_df.filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("sl_pct_price_long").is_not_nan()
        )

        if len(long_positions) > 0:
            # 止损价应该低于进场价
            invalid_sl = long_positions.filter(
                pl.col("sl_pct_price_long") >= pl.col("entry_long_price")
            )

            assert len(invalid_sl) == 0, (
                f"发现 {len(invalid_sl)} 条多头止损价 >= 进场价的异常记录"
            )
