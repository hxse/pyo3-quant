"""
精细化测试: 资金状态一致性验证

验证 balance, equity, trade_pnl_pct, total_return_pct 之间的数学关系:

核心公式 (来自 capital_calculator.rs):
    1. equity = balance * (1 + unrealized_pnl_pct)
       - 无持仓: unrealized_pnl_pct = 0, 即 equity = balance
       - 持多头: unrealized_pnl_pct = (close - entry_long) / entry_long
       - 持空头: unrealized_pnl_pct = (entry_short - close) / entry_short

    2. total_return_pct = equity / initial_capital - 1

    3. balance 连续性:
       - 离场时: balance = prev_balance * (1 + trade_pnl_pct)
       - 非离场时: balance = prev_balance
"""

import polars as pl
import pytest


class TestEquityCalculation:
    """测试 equity 的计算正确性"""

    def test_equity_no_position(self, backtest_df, backtest_params):
        """验证无持仓时 equity = balance"""
        # 无持仓: entry_long 和 entry_short 都是 NaN
        df = backtest_df.filter(
            pl.col("entry_long_price").is_nan() & pl.col("entry_short_price").is_nan()
        )

        if len(df) == 0:
            pytest.skip("无空仓记录")

        df = df.with_columns(
            (pl.col("equity") - pl.col("balance")).abs().alias("equity_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("equity_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ 空仓时 equity != balance (前5条):")
            print(errors.select(["balance", "equity", "equity_diff"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处 equity 计算错误")

        print(f"✅ {len(df)} 行空仓时 equity = balance 验证通过")

    def test_equity_long_position(self, backtest_df, backtest_params):
        """验证持多头时 equity = balance * (1 + (close - entry) / entry)"""
        # 持多头: entry_long 存在且 exit_long 不存在
        df = backtest_df.filter(
            pl.col("entry_long_price").is_not_nan() & pl.col("exit_long_price").is_nan()
        )

        if len(df) == 0:
            pytest.skip("无多头持仓记录")

        df = (
            df.with_columns(
                (
                    (pl.col("close") - pl.col("entry_long_price"))
                    / pl.col("entry_long_price")
                ).alias("unrealized_pnl_pct")
            )
            .with_columns(
                (pl.col("balance") * (1.0 + pl.col("unrealized_pnl_pct"))).alias(
                    "expected_equity"
                )
            )
            .with_columns(
                (pl.col("equity") - pl.col("expected_equity"))
                .abs()
                .alias("equity_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("equity_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ 多头 equity 计算错误 (前5条):")
            print(
                errors.select(
                    ["balance", "equity", "expected_equity", "equity_diff"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处多头 equity 计算错误")

        print(f"✅ {len(df)} 行多头持仓 equity 计算正确")

    def test_equity_short_position(self, backtest_df, backtest_params):
        """验证持空头时 equity = balance * (1 + (entry - close) / entry)"""
        # 持空头: entry_short 存在且 exit_short 不存在
        df = backtest_df.filter(
            pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_nan()
        )

        if len(df) == 0:
            pytest.skip("无空头持仓记录")

        df = (
            df.with_columns(
                (
                    (pl.col("entry_short_price") - pl.col("close"))
                    / pl.col("entry_short_price")
                ).alias("unrealized_pnl_pct")
            )
            .with_columns(
                (pl.col("balance") * (1.0 + pl.col("unrealized_pnl_pct"))).alias(
                    "expected_equity"
                )
            )
            .with_columns(
                (pl.col("equity") - pl.col("expected_equity"))
                .abs()
                .alias("equity_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("equity_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ 空头 equity 计算错误 (前5条):")
            print(
                errors.select(
                    ["balance", "equity", "expected_equity", "equity_diff"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处空头 equity 计算错误")

        print(f"✅ {len(df)} 行空头持仓 equity 计算正确")


class TestTotalReturnPctCalculation:
    """测试 total_return_pct 的计算正确性"""

    def test_total_return_pct_formula(self, backtest_df, backtest_params):
        """验证 total_return_pct = equity / initial_capital - 1"""
        initial_capital = backtest_params.initial_capital

        df = backtest_df.with_columns(
            (pl.col("equity") / initial_capital - 1.0).alias("expected_total_return")
        ).with_columns(
            (pl.col("total_return_pct") - pl.col("expected_total_return"))
            .abs()
            .alias("return_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("return_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ total_return_pct 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "equity",
                        "total_return_pct",
                        "expected_total_return",
                        "return_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 total_return_pct 计算错误")

        print(f"✅ {len(df)} 行 total_return_pct 计算正确")

    def test_total_return_pct_initial(self, backtest_df, backtest_params):
        """验证初始状态的 total_return_pct"""
        # 第一行应该是初始状态
        first_row = backtest_df.head(1)
        initial_capital = backtest_params.initial_capital

        equity = first_row["equity"][0]
        total_return = first_row["total_return_pct"][0]
        expected_return = equity / initial_capital - 1.0

        diff = abs(total_return - expected_return)
        assert diff < 1e-10, (
            f"初始 total_return_pct 错误: {total_return} != {expected_return}"
        )

        print(f"✅ 初始 total_return_pct = {total_return:.6f} 正确")

    def test_balance_total_return_relationship_on_exit(
        self, backtest_df, backtest_params
    ):
        """验证离场时 balance 和 total_return_pct 的变动关系

        离场时 equity = balance，所以:
            balance = initial_capital * (1 + total_return_pct)

        变动关系:
            balance_change = initial_capital * total_return_change
        """
        initial_capital = backtest_params.initial_capital

        # 纯离场状态（排除反手）
        is_pure_long_exit = (
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
            & pl.col("entry_short_price").is_nan()
            & pl.col("exit_short_price").is_nan()
        )
        is_pure_short_exit = (
            pl.col("entry_long_price").is_nan()
            & pl.col("exit_long_price").is_nan()
            & pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
        )

        df = backtest_df.with_columns(
            [
                pl.col("balance").shift(1).alias("prev_balance"),
                pl.col("total_return_pct").shift(1).alias("prev_total_return_pct"),
            ]
        ).filter(
            (is_pure_long_exit | is_pure_short_exit)
            & pl.col("prev_balance").is_not_null()
            & pl.col("prev_total_return_pct").is_not_null()
        )

        if len(df) == 0:
            pytest.skip("无纯离场记录")

        # 验证 balance = initial_capital * (1 + total_return_pct)
        df = df.with_columns(
            (initial_capital * (1 + pl.col("total_return_pct"))).alias(
                "expected_balance"
            )
        ).with_columns(
            (pl.col("balance") - pl.col("expected_balance")).abs().alias("balance_diff")
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ balance = initial_capital * (1 + total_return_pct) 不成立:")
            print(
                errors.select(
                    ["balance", "expected_balance", "total_return_pct", "balance_diff"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处关系错误")

        print(f"✅ {len(df)} 行离场时 balance 与 total_return_pct 关系正确")


class TestCumulativeCalculations:
    """测试累积计算的正确性"""

    def test_balance_equals_cumprod_trade_pnl(self, backtest_df, backtest_params):
        """验证余额等于初始资金乘以累积的 (1 + trade_pnl_pct)

        公式: balance = initial_capital × cumprod(1 + trade_pnl_pct)

        注意:
        - trade_pnl_pct 在非离场时为 0，所以 (1 + 0) = 1 不影响累积
        - 爆仓后 (balance = 0) 公式不再适用，需要排除
        """
        initial_capital = backtest_params.initial_capital

        # 找到第一次爆仓的位置，只验证爆仓前的数据
        first_zero_idx = backtest_df.with_row_index("idx").filter(
            pl.col("balance") == 0
        )

        if len(first_zero_idx) > 0:
            # 只取爆仓前的数据
            max_valid_idx = first_zero_idx["idx"].min()
            df = backtest_df.head(max_valid_idx)
        else:
            df = backtest_df

        if len(df) == 0:
            pytest.skip("无有效数据（可能第一行就爆仓）")

        # 计算累积乘积
        df = (
            df.with_columns(
                (1 + pl.col("trade_pnl_pct")).cum_prod().alias("cumprod_factor")
            )
            .with_columns(
                (initial_capital * pl.col("cumprod_factor")).alias("expected_balance")
            )
            .with_columns(
                (pl.col("balance") - pl.col("expected_balance"))
                .abs()
                .alias("balance_diff")
            )
        )

        tolerance = 1e-6  # 累积计算可能有浮点误差
        errors = df.filter(pl.col("balance_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ balance = initial_capital × cumprod(1 + trade_pnl_pct) 不成立:")
            print(
                errors.select(
                    [
                        "balance",
                        "expected_balance",
                        "trade_pnl_pct",
                        "cumprod_factor",
                        "balance_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处累积计算错误")

        print(f"✅ {len(df)} 行余额与累积盈亏关系正确（爆仓前）")

    def test_total_return_from_cumprod(self, backtest_df, backtest_params):
        """验证总回报等于累积的 (1 + trade_pnl_pct) - 1（离场时）

        离场时 equity = balance，所以:
            total_return_pct = balance / initial_capital - 1
                             = cumprod(1 + trade_pnl_pct) - 1

        注意：爆仓后 (balance = 0) 公式不再适用，需要排除
        """

        # 找到第一次爆仓的位置，只验证爆仓前的数据
        first_zero_idx = backtest_df.with_row_index("idx").filter(
            pl.col("balance") == 0
        )

        if len(first_zero_idx) > 0:
            max_valid_idx = first_zero_idx["idx"].min()
            df_valid = backtest_df.head(max_valid_idx)
        else:
            df_valid = backtest_df

        if len(df_valid) == 0:
            pytest.skip("无有效数据（可能第一行就爆仓）")

        # 纯离场状态（equity = balance）
        is_pure_long_exit = (
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
            & pl.col("entry_short_price").is_nan()
            & pl.col("exit_short_price").is_nan()
        )
        is_pure_short_exit = (
            pl.col("entry_long_price").is_nan()
            & pl.col("exit_long_price").is_nan()
            & pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
        )

        df = df_valid.with_columns(
            (1 + pl.col("trade_pnl_pct")).cum_prod().alias("cumprod_factor")
        ).filter(is_pure_long_exit | is_pure_short_exit)

        if len(df) == 0:
            pytest.skip("无纯离场记录")

        df = df.with_columns(
            (pl.col("cumprod_factor") - 1.0).alias("expected_total_return")
        ).with_columns(
            (pl.col("total_return_pct") - pl.col("expected_total_return"))
            .abs()
            .alias("return_diff")
        )

        tolerance = 1e-6
        errors = df.filter(pl.col("return_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ total_return_pct = cumprod(1 + trade_pnl_pct) - 1 不成立:")
            print(
                errors.select(
                    [
                        "total_return_pct",
                        "expected_total_return",
                        "cumprod_factor",
                        "return_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处累积计算错误")

        print(f"✅ {len(df)} 行离场时总回报与累积盈亏关系正确（爆仓前）")


class TestBalanceEquityCrossValidation:
    """测试 balance 和 equity 的交叉验证"""

    def test_equity_on_exit_equals_balance(self, backtest_df, backtest_params):
        """验证纯离场时 equity = balance（排除反手状态）

        状态 8/9（反手）离场后立即有新仓位，所以 equity != balance
        只验证纯离场状态（状态 4/5/6/7）
        """
        # 纯多头离场: 只有 long 有 entry 和 exit，short 都是 NaN
        is_pure_long_exit = (
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_not_nan()
            & pl.col("entry_short_price").is_nan()
            & pl.col("exit_short_price").is_nan()
        )
        # 纯空头离场: 只有 short 有 entry 和 exit，long 都是 NaN
        is_pure_short_exit = (
            pl.col("entry_long_price").is_nan()
            & pl.col("exit_long_price").is_nan()
            & pl.col("entry_short_price").is_not_nan()
            & pl.col("exit_short_price").is_not_nan()
        )

        df = backtest_df.filter(is_pure_long_exit | is_pure_short_exit)

        if len(df) == 0:
            pytest.skip("无纯离场记录（排除反手状态后）")

        df = df.with_columns((pl.col("equity") - pl.col("balance")).abs().alias("diff"))

        tolerance = 1e-10
        errors = df.filter(pl.col("diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ 纯离场时 equity != balance (前5条):")
            print(errors.select(["balance", "equity", "diff"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处纯离场时 equity 错误")

        print(f"✅ {len(df)} 行纯离场时 equity = balance 验证通过")

    def test_trade_pnl_pct_zero_when_no_exit(self, backtest_df, backtest_params):
        """验证非离场时 trade_pnl_pct = 0"""
        # 非离场行: exit_long 和 exit_short 都是 NaN
        df = backtest_df.filter(
            pl.col("exit_long_price").is_nan() & pl.col("exit_short_price").is_nan()
        )

        if len(df) == 0:
            pytest.skip("无非离场记录")

        errors = df.filter(pl.col("trade_pnl_pct") != 0.0)

        if len(errors) > 0:
            print("\n❌ 非离场时 trade_pnl_pct != 0 (前5条):")
            print(errors.select(["trade_pnl_pct"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处非离场时 trade_pnl_pct 非零")

        print(f"✅ {len(df)} 行非离场时 trade_pnl_pct = 0 验证通过")


class TestDrawdownCalculation:
    """测试回撤计算的正确性"""

    def test_current_drawdown_formula(self, backtest_df, backtest_params):
        """验证 current_drawdown = (peak_equity - equity) / peak_equity"""
        # 计算滚动最高 equity
        df = (
            backtest_df.with_columns(pl.col("equity").cum_max().alias("expected_peak"))
            .with_columns(
                pl.when(pl.col("expected_peak") > 0)
                .then(
                    (pl.col("expected_peak") - pl.col("equity"))
                    / pl.col("expected_peak")
                )
                .otherwise(0.0)
                .alias("expected_drawdown")
            )
            .with_columns(
                (pl.col("current_drawdown") - pl.col("expected_drawdown"))
                .abs()
                .alias("drawdown_diff")
            )
        )

        tolerance = 1e-10
        errors = df.filter(pl.col("drawdown_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ current_drawdown 计算错误 (前5条):")
            print(
                errors.select(
                    ["equity", "current_drawdown", "expected_drawdown", "drawdown_diff"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 current_drawdown 计算错误")

        print(f"✅ {len(df)} 行 current_drawdown 计算正确")

    def test_drawdown_non_negative(self, backtest_df, backtest_params):
        """验证 current_drawdown >= 0"""
        errors = backtest_df.filter(pl.col("current_drawdown") < 0)

        if len(errors) > 0:
            print("\n❌ current_drawdown 出现负值:")
            print(errors.select(["current_drawdown"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处 current_drawdown 为负")

        print("✅ current_drawdown 非负验证通过")

    def test_drawdown_max_one(self, backtest_df, backtest_params):
        """验证 current_drawdown <= 1 (最多 100% 回撤)"""
        errors = backtest_df.filter(pl.col("current_drawdown") > 1.0)

        if len(errors) > 0:
            print("\n❌ current_drawdown > 1:")
            print(errors.select(["current_drawdown"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处 current_drawdown > 1")

        print("✅ current_drawdown <= 1 验证通过")
