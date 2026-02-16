"""
精细化测试: fee 计算验证 (矢量化版本)

验证公式 (来自 capital_calculator.rs):
    单次结算: fee = fee_fixed + initial_balance * fee_pct / 2 + realized_value * fee_pct / 2
    多次结算: fee = sum(单次 fee)  # 状态 10/11 涉及两次结算
"""

import polars as pl
import pytest


def _is_reversal_then_exit(df: pl.DataFrame) -> pl.Expr:
    """判断是否是反手后立即风控离场的状态 (状态 10/11)"""
    # 状态 10/11: 同时有 long 和 short 的进场和离场，且 in_bar_direction != 0
    return (
        pl.col("entry_long_price").is_not_nan()
        & pl.col("exit_long_price").is_not_nan()
        & pl.col("entry_short_price").is_not_nan()
        & pl.col("exit_short_price").is_not_nan()
        & (pl.col("risk_in_bar_direction") != 0)
    )


def _calculate_two_leg_fee(
    prev_balance: float,
    entry1: float,
    exit1: float,
    entry2: float,
    exit2: float,
    is_first_long: bool,
    fee_fixed: float,
    fee_pct: float,
) -> float:
    """计算两次结算的综合 fee

    Args:
        is_first_long: True 表示先结算多头（状态 11），False 表示先结算空头（状态 10）
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

    return fee1 + fee2


class TestFeeCalculation:
    """测试手续费计算的数学正确性 (矢量化)"""

    def test_long_exit_fee_calculation(self, backtest_df, backtest_params):
        """验证多头离场的 fee 计算（排除状态 10/11）"""
        fee_fixed = backtest_params.fee_fixed
        fee_pct = backtest_params.fee_pct

        # 排除状态 10/11（这些行在专门的测试中验证）
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
                ).alias("expected_fee")
            )
            .with_columns(
                (pl.col("fee") - pl.col("expected_fee")).abs().alias("fee_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("fee_diff") > tolerance)

        if len(errors) > 0:
            pytest.fail(f"发现 {len(errors)} 处 fee 计算错误")

    def test_short_exit_fee_calculation(self, backtest_df, backtest_params):
        """验证空头离场的 fee 计算（排除状态 10/11）"""
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
                ).alias("expected_fee")
            )
            .with_columns(
                (pl.col("fee") - pl.col("expected_fee")).abs().alias("fee_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("fee_diff") > tolerance)

        if len(errors) > 0:
            pytest.fail(f"发现 {len(errors)} 处 fee 计算错误")

    def test_reversal_then_exit_fee_calculation(self, backtest_df, backtest_params):
        """验证状态 10/11（反手后风控离场）的综合 fee 计算"""
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

        # 矢量化计算预期的综合 fee
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
        total_fee_state10 = fee1_state10 + fee2_state10

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
        total_fee_state11 = fee1_state11 + fee2_state11

        df = df.with_columns(
            pl.when(pl.col("risk_in_bar_direction") == 1)
            .then(total_fee_state10)
            .otherwise(total_fee_state11)
            .alias("expected_fee")
        ).with_columns((pl.col("fee") - pl.col("expected_fee")).abs().alias("fee_diff"))

        tolerance = 1e-10
        errors = df.filter(pl.col("fee_diff") > tolerance)

        if len(errors) > 0:
            pytest.fail(f"发现 {len(errors)} 处综合 fee 计算错误")


class TestFeeCumCalculation:
    """测试手续费累积的数学正确性 (矢量化)

    验证公式:
        fee_cum[i] = fee_cum[i-1] + fee[i]
    """

    def test_fee_cum_accumulation(self, backtest_df, backtest_params):
        """验证 fee_cum 是 fee 的正确累积"""
        # 计算预期的累积手续费
        df = backtest_df.with_columns(
            pl.col("fee").cum_sum().alias("expected_fee_cum")
        ).with_columns(
            (pl.col("fee_cum") - pl.col("expected_fee_cum")).abs().alias("cum_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("cum_diff") > tolerance)

        if len(errors) > 0:
            pytest.fail(f"发现 {len(errors)} 处 fee 累积错误")

        total_fee = df["fee_cum"].max()

    def test_fee_cum_monotonic(self, backtest_df, backtest_params):
        """验证 fee_cum 单调递增（或不变）"""
        # fee >= 0，所以 fee_cum 应该单调不减
        is_monotonic = backtest_df["fee_cum"].is_sorted()

        assert is_monotonic, "fee_cum 应该单调递增"
