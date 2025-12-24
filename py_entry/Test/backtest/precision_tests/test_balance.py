"""
精细化测试: balance 更新验证 (矢量化版本)

验证公式:
    balance = max(0, prev_balance * (1 + trade_pnl_pct))

注意: 源代码有归零保护，balance 不会变为负数
"""

import polars as pl
import pytest


class TestBalanceCalculation:
    """测试余额更新的数学正确性 (矢量化)"""

    def test_long_exit_balance_update(self, backtest_df, backtest_params):
        """验证多头离场后的 balance 更新"""
        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
        )

        if len(df) == 0:
            pytest.skip("无多头离场记录")

        df = df.with_columns(
            pl.max_horizontal(
                pl.lit(0.0),
                pl.col("prev_balance") * (1.0 + pl.col("trade_pnl_pct")),
            ).alias("expected_balance")
        ).with_columns(
            (pl.col("balance") - pl.col("expected_balance")).abs().alias("balance_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ Balance 更新错误 (前5条):")
            print(
                errors.select(
                    [
                        "prev_balance",
                        "trade_pnl_pct",
                        "balance",
                        "expected_balance",
                        "balance_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 balance 更新错误")

        print(f"✅ {len(df)} 笔多头离场的 balance 更新正确")

    def test_short_exit_balance_update(self, backtest_df, backtest_params):
        """验证空头离场后的 balance 更新"""
        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
        )

        if len(df) == 0:
            pytest.skip("无空头离场记录")

        df = df.with_columns(
            pl.max_horizontal(
                pl.lit(0.0),
                pl.col("prev_balance") * (1.0 + pl.col("trade_pnl_pct")),
            ).alias("expected_balance")
        ).with_columns(
            (pl.col("balance") - pl.col("expected_balance")).abs().alias("balance_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ Balance 更新错误 (前5条):")
            print(
                errors.select(
                    [
                        "prev_balance",
                        "trade_pnl_pct",
                        "balance",
                        "expected_balance",
                        "balance_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 balance 更新错误")

        print(f"✅ {len(df)} 笔空头离场的 balance 更新正确")


class TestBalanceAccumulation:
    """测试余额累积的一致性 (矢量化)

    验证规则:
    - 无交易时 (trade_pnl_pct == 0): balance 保持不变
    - 有交易时: balance = prev_balance * (1 + trade_pnl_pct)
    - 相邻行的 balance 应该连续（除非有交易）
    """

    def test_balance_unchanged_when_no_trade(self, backtest_df, backtest_params):
        """验证无交易时 balance 保持不变"""
        # 筛选 trade_pnl_pct == 0 的行（无交易）
        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            (pl.col("trade_pnl_pct") == 0.0)
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
        )

        if len(df) == 0:
            pytest.skip("无 trade_pnl_pct == 0 的记录")

        # 无交易时，balance 应该等于 prev_balance
        df = df.with_columns(
            (pl.col("balance") - pl.col("prev_balance")).abs().alias("balance_diff")
        )

        tolerance = 0
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ Balance 累积错误 (无交易时应保持不变):")
            print(errors.select(["prev_balance", "balance", "trade_pnl_pct"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处 balance 在无交易时发生变化")

        print(f"✅ {len(df)} 行无交易时 balance 正确保持不变")

    def test_balance_continuity(self, backtest_df, backtest_params):
        """验证 balance 累积的连续性

        规则:
        - 离场行: balance = max(0, prev_balance * (1 + trade_pnl_pct))
        - 非离场行: balance = prev_balance (保持不变)
        """
        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            pl.col("prev_balance").is_not_null() & pl.col("prev_balance").is_not_nan()
        )

        # 判断是否为离场行
        is_long_exit = (
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
        )
        is_short_exit = (
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
        )
        is_exit_row = is_long_exit | is_short_exit

        # 计算预期 balance
        df = df.with_columns(
            pl.when(is_exit_row)
            .then(
                pl.max_horizontal(
                    pl.lit(0.0),
                    pl.col("prev_balance") * (1.0 + pl.col("trade_pnl_pct")),
                )
            )
            .otherwise(pl.col("prev_balance"))
            .alias("expected_balance")
        ).with_columns(
            (pl.col("balance") - pl.col("expected_balance")).abs().alias("balance_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ Balance 连续性错误:")
            print(
                errors.select(
                    ["prev_balance", "trade_pnl_pct", "balance", "expected_balance"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 balance 连续性错误")

        print(f"✅ {len(df)} 行 balance 连续性验证通过")
