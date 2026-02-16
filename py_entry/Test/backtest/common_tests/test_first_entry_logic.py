"""测试首次进场标记逻辑"""

import polars as pl
import pytest


class TestFirstEntryRiskPrices:
    """测试首次进场时 Risk 价格设置"""

    def test_sl_price_set_on_entry(self, backtest_df):
        """测试止损价格在进场时设置"""
        # 找到进场记录 (直接使用 first_entry_side == 1)
        long_entries = backtest_df.with_row_index("idx").filter(
            pl.col("first_entry_side") == 1
        )

        if len(long_entries) > 0 and "sl_pct_price_long" in backtest_df.columns:
            # 检查进场时是否设置了止损
            entries_with_sl = long_entries.filter(
                pl.col("sl_pct_price_long").is_not_nan()
            )

            # 至少应该有一些进场设置了止损
            if len(long_entries) > 0:
                assert len(entries_with_sl) > 0, "进场时应设置止损价格"

    def test_tp_price_set_on_entry(self, backtest_df):
        """测试止盈价格在进场时设置"""
        long_entries = backtest_df.filter(pl.col("first_entry_side") == 1)

        if len(long_entries) > 0 and "tp_pct_price_long" in backtest_df.columns:
            entries_with_tp = long_entries.filter(
                pl.col("tp_pct_price_long").is_not_nan()
            )

            if len(long_entries) > 0:
                assert len(entries_with_tp) > 0, "进场时应设置止盈价格"

    def test_tsl_price_updates(self, backtest_df):
        """测试跟踪止损价格更新"""
        if "tsl_pct_price_long" not in backtest_df.columns:
            pytest.skip("未启用跟踪止损")

        # 找到持有多头的序列
        hold_long = backtest_df.filter(
            pl.col("entry_long_price").is_not_nan() & pl.col("exit_long_price").is_nan()
        )

        if len(hold_long) > 0:
            # TSL 应该随着价格更新
            tsl_with_values = hold_long.filter(
                pl.col("tsl_pct_price_long").is_not_nan()
            )
