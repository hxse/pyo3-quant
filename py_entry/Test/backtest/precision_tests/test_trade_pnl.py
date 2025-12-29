"""
精细化测试: trade_pnl_pct 计算验证 (矢量化版本)

验证公式 (来自 capital_calculator.rs):
    单次结算:
        pnl_raw_pct = (exit_price - entry_price) / entry_price  (多头)
        pnl_raw_pct = (entry_price - exit_price) / entry_price  (空头)
        realized_value = initial_balance * (1 + pnl_raw_pct)
        fee = fee_fixed + initial_balance * fee_pct / 2 + realized_value * fee_pct / 2
        new_balance = realized_value - fee
        trade_pnl_pct = new_balance / initial_balance - 1

    多次结算 (状态 10/11):
        trade_pnl_pct = final_balance / bar_start_balance - 1
"""

import polars as pl
import pytest


def _is_reversal_then_exit(df: pl.DataFrame) -> pl.Expr:
    """判断是否是反手后立即风控离场的状态 (状态 10/11)"""
    return (
        pl.col("entry_long_price").is_not_nan()
        & pl.col("exit_long_price").is_not_nan()
        & pl.col("entry_short_price").is_not_nan()
        & pl.col("exit_short_price").is_not_nan()
        & (pl.col("risk_in_bar_direction") != 0)
    )


def _calculate_two_leg_pnl_pct(
    prev_balance: float,
    entry1: float,
    exit1: float,
    entry2: float,
    exit2: float,
    is_first_long: bool,
    fee_fixed: float,
    fee_pct: float,
) -> float:
    """计算两次结算的综合 trade_pnl_pct

    Args:
        is_first_long: True 表示先结算多头（状态 11），False 表示先结算空头（状态 10）

    Returns:
        综合 trade_pnl_pct = final_balance / prev_balance - 1
    """
    if is_first_long:
        # 状态 11: 先平多头，再平空头（风控）
        # 第一次：多头离场
        pnl1_pct = (exit1 - entry1) / entry1
        realized1 = prev_balance * (1.0 + pnl1_pct)
        fee1 = fee_fixed + prev_balance * fee_pct / 2.0 + realized1 * fee_pct / 2.0
        balance_after_1 = realized1 - fee1

        # 第二次：空头离场（风控）
        pnl2_pct = (entry2 - exit2) / entry2
        realized2 = balance_after_1 * (1.0 + pnl2_pct)
        fee2 = fee_fixed + balance_after_1 * fee_pct / 2.0 + realized2 * fee_pct / 2.0
        final_balance = realized2 - fee2
    else:
        # 状态 10: 先平空头，再平多头（风控）
        # 第一次：空头离场
        pnl1_pct = (entry1 - exit1) / entry1
        realized1 = prev_balance * (1.0 + pnl1_pct)
        fee1 = fee_fixed + prev_balance * fee_pct / 2.0 + realized1 * fee_pct / 2.0
        balance_after_1 = realized1 - fee1

        # 第二次：多头离场（风控）
        pnl2_pct = (exit2 - entry2) / entry2
        realized2 = balance_after_1 * (1.0 + pnl2_pct)
        fee2 = fee_fixed + balance_after_1 * fee_pct / 2.0 + realized2 * fee_pct / 2.0
        final_balance = realized2 - fee2

    return final_balance / prev_balance - 1.0


class TestTradePnlPctCalculation:
    """测试单笔盈亏百分比计算的数学正确性 (矢量化)"""

    def test_long_exit_trade_pnl_pct(self, backtest_df, backtest_params):
        """验证多头离场的 trade_pnl_pct 计算（排除状态 10/11）"""
        fee_fixed = backtest_params.fee_fixed
        fee_pct = backtest_params.fee_pct

        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
            # 排除状态 10/11
            & ~_is_reversal_then_exit(backtest_df)
        )

        if len(df) == 0:
            pytest.skip("无多头离场记录（排除状态 10/11 后）")

        df = (
            df.with_columns(
                (
                    (pl.col("exit_long_price") - pl.col("entry_long_price"))
                    / pl.col("entry_long_price")
                ).alias("pnl_raw_pct")
            )
            .with_columns(
                (pl.col("prev_balance") * (1.0 + pl.col("pnl_raw_pct"))).alias(
                    "realized_value"
                )
            )
            .with_columns(
                (
                    pl.lit(fee_fixed)
                    + pl.col("prev_balance") * fee_pct / 2.0
                    + pl.col("realized_value") * fee_pct / 2.0
                ).alias("calc_fee")
            )
            .with_columns(
                (pl.col("realized_value") - pl.col("calc_fee")).alias("new_balance")
            )
            .with_columns(
                (pl.col("new_balance") / pl.col("prev_balance") - 1.0).alias(
                    "expected_pnl_pct"
                )
            )
            .with_columns(
                (pl.col("trade_pnl_pct") - pl.col("expected_pnl_pct"))
                .abs()
                .alias("pnl_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("pnl_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ trade_pnl_pct 计算错误 (前5条):")
            print(
                errors.select(["trade_pnl_pct", "expected_pnl_pct", "pnl_diff"]).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 trade_pnl_pct 计算错误")

        print(f"✅ {len(df)} 笔多头离场的 trade_pnl_pct 计算正确")

    def test_short_exit_trade_pnl_pct(self, backtest_df, backtest_params):
        """验证空头离场的 trade_pnl_pct 计算（排除状态 10/11）"""
        fee_fixed = backtest_params.fee_fixed
        fee_pct = backtest_params.fee_pct

        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
            # 排除状态 10/11
            & ~_is_reversal_then_exit(backtest_df)
        )

        if len(df) == 0:
            pytest.skip("无空头离场记录（排除状态 10/11 后）")

        df = (
            df.with_columns(
                (
                    (pl.col("entry_short_price") - pl.col("exit_short_price"))
                    / pl.col("entry_short_price")
                ).alias("pnl_raw_pct")
            )
            .with_columns(
                (pl.col("prev_balance") * (1.0 + pl.col("pnl_raw_pct"))).alias(
                    "realized_value"
                )
            )
            .with_columns(
                (
                    pl.lit(fee_fixed)
                    + pl.col("prev_balance") * fee_pct / 2.0
                    + pl.col("realized_value") * fee_pct / 2.0
                ).alias("calc_fee")
            )
            .with_columns(
                (pl.col("realized_value") - pl.col("calc_fee")).alias("new_balance")
            )
            .with_columns(
                (pl.col("new_balance") / pl.col("prev_balance") - 1.0).alias(
                    "expected_pnl_pct"
                )
            )
            .with_columns(
                (pl.col("trade_pnl_pct") - pl.col("expected_pnl_pct"))
                .abs()
                .alias("pnl_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("pnl_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ trade_pnl_pct 计算错误 (前5条):")
            print(
                errors.select(["trade_pnl_pct", "expected_pnl_pct", "pnl_diff"]).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 trade_pnl_pct 计算错误")

        print(f"✅ {len(df)} 笔空头离场的 trade_pnl_pct 计算正确")

    def test_reversal_then_exit_trade_pnl_pct(self, backtest_df, backtest_params):
        """验证状态 10/11（反手后风控离场）的综合 trade_pnl_pct 计算"""
        fee_fixed = backtest_params.fee_fixed
        fee_pct = backtest_params.fee_pct

        df = backtest_df.with_columns(
            pl.col("balance").shift(1).alias("prev_balance")
        ).filter(
            _is_reversal_then_exit(backtest_df)
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_balance").is_not_nan()
        )

        if len(df) == 0:
            pytest.skip("无状态 10/11（反手后风控离场）记录")

        # 矢量化计算预期的综合 trade_pnl_pct
        # 状态 10: 空转多 + 多头风控 (in_bar_direction == 1)
        # 第一次：空头离场
        pnl1_pct_state10 = (
            pl.col("entry_short_price") - pl.col("exit_short_price")
        ) / pl.col("entry_short_price")
        realized1_state10 = pl.col("prev_balance") * (1.0 + pnl1_pct_state10)
        fee1_state10 = (
            pl.lit(fee_fixed)
            + pl.col("prev_balance") * fee_pct / 2.0
            + realized1_state10 * fee_pct / 2.0
        )
        balance_after_1_state10 = realized1_state10 - fee1_state10

        # 第二次：多头离场（风控）
        pnl2_pct_state10 = (
            pl.col("exit_long_price") - pl.col("entry_long_price")
        ) / pl.col("entry_long_price")
        realized2_state10 = balance_after_1_state10 * (1.0 + pnl2_pct_state10)
        fee2_state10 = (
            pl.lit(fee_fixed)
            + balance_after_1_state10 * fee_pct / 2.0
            + realized2_state10 * fee_pct / 2.0
        )
        final_balance_state10 = realized2_state10 - fee2_state10
        expected_pnl_state10 = final_balance_state10 / pl.col("prev_balance") - 1.0

        # 状态 11: 多转空 + 空头风控 (in_bar_direction == -1)
        # 第一次：多头离场
        pnl1_pct_state11 = (
            pl.col("exit_long_price") - pl.col("entry_long_price")
        ) / pl.col("entry_long_price")
        realized1_state11 = pl.col("prev_balance") * (1.0 + pnl1_pct_state11)
        fee1_state11 = (
            pl.lit(fee_fixed)
            + pl.col("prev_balance") * fee_pct / 2.0
            + realized1_state11 * fee_pct / 2.0
        )
        balance_after_1_state11 = realized1_state11 - fee1_state11

        # 第二次：空头离场（风控）
        pnl2_pct_state11 = (
            pl.col("entry_short_price") - pl.col("exit_short_price")
        ) / pl.col("entry_short_price")
        realized2_state11 = balance_after_1_state11 * (1.0 + pnl2_pct_state11)
        fee2_state11 = (
            pl.lit(fee_fixed)
            + balance_after_1_state11 * fee_pct / 2.0
            + realized2_state11 * fee_pct / 2.0
        )
        final_balance_state11 = realized2_state11 - fee2_state11
        expected_pnl_state11 = final_balance_state11 / pl.col("prev_balance") - 1.0

        df = df.with_columns(
            pl.when(pl.col("risk_in_bar_direction") == 1)
            .then(expected_pnl_state10)
            .otherwise(expected_pnl_state11)
            .alias("expected_pnl_pct")
        ).with_columns(
            (pl.col("trade_pnl_pct") - pl.col("expected_pnl_pct"))
            .abs()
            .alias("pnl_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("pnl_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ 状态 10/11 综合 trade_pnl_pct 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "risk_in_bar_direction",
                        "trade_pnl_pct",
                        "expected_pnl_pct",
                        "pnl_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处综合 trade_pnl_pct 计算错误")

        print(f"✅ {len(df)} 笔状态 10/11 的综合 trade_pnl_pct 计算正确")
