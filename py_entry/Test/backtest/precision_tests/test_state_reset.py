"""
精细化测试: 状态重置验证

验证回测中各种状态的重置逻辑是否正确:

1. 每 bar 重置:
   - 非离场时 trade_pnl_pct = 0
   - 非离场时 fee = 0

2. risk_in_bar_direction 一致性:
   - in_bar=1 时必须有 exit_long_price
   - in_bar=-1 时必须有 exit_short_price

3. 风控价格在同一笔交易中的行为:
   - SL/TP 价格在同一笔交易期间保持不变
   - TSL 价格在同一笔交易期间只能向有利方向移动
"""

import polars as pl
import pytest


class TestPerBarReset:
    """测试每 bar 重置的正确性"""

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

    def test_fee_zero_when_no_exit(self, backtest_df, backtest_params):
        """验证非离场时 fee = 0"""
        # 非离场行: exit_long 和 exit_short 都是 NaN
        df = backtest_df.filter(
            pl.col("exit_long_price").is_nan() & pl.col("exit_short_price").is_nan()
        )

        if len(df) == 0:
            pytest.skip("无非离场记录")

        errors = df.filter(pl.col("fee") != 0.0)

        if len(errors) > 0:
            print("\n❌ 非离场时 fee != 0 (前5条):")
            print(errors.select(["fee"]).head(5))
            pytest.fail(f"发现 {len(errors)} 处非离场时 fee 非零")

        print(f"✅ {len(df)} 行非离场时 fee = 0 验证通过")


class TestInBarDirectionReset:
    """测试 in_bar_direction 重置的正确性"""

    def test_in_bar_direction_consistency(self, backtest_df, backtest_params):
        """验证 risk_in_bar_direction 与离场状态一致"""
        # in_bar = 1: 必须有 exit_long
        # in_bar = -1: 必须有 exit_short
        # in_bar = 0: 可以有任何状态

        in_bar_1_no_exit = backtest_df.filter(
            (pl.col("risk_in_bar_direction") == 1) & pl.col("exit_long_price").is_nan()
        )

        in_bar_neg1_no_exit = backtest_df.filter(
            (pl.col("risk_in_bar_direction") == -1)
            & pl.col("exit_short_price").is_nan()
        )

        if len(in_bar_1_no_exit) > 0:
            print("\n❌ in_bar=1 但无 exit_long:")
            print(in_bar_1_no_exit.head(5))
            pytest.fail(f"发现 {len(in_bar_1_no_exit)} 处 in_bar=1 但无多头离场")

        if len(in_bar_neg1_no_exit) > 0:
            print("\n❌ in_bar=-1 但无 exit_short:")
            print(in_bar_neg1_no_exit.head(5))
            pytest.fail(f"发现 {len(in_bar_neg1_no_exit)} 处 in_bar=-1 但无空头离场")

        print("✅ risk_in_bar_direction 与离场状态一致")


class TestRiskPriceInSameTrade:
    """测试同一笔交易期间的风控价格行为"""

    def test_sl_atr_price_stable_in_same_trade(self, backtest_with_config):
        """验证 SL ATR 价格在同一笔交易期间保持不变

        通过给每笔交易分配唯一 ID，然后验证同一交易内的 SL 价格一致
        """
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        if backtest_params.sl_atr is None or backtest_params.sl_atr.value == 0:
            pytest.skip("策略未启用 sl_atr")

        df = results[0].backtest_result

        if "sl_atr_price_long" not in df.columns:
            pytest.skip("回测结果无 sl_atr_price_long 列")

        # 给每笔多头交易分配唯一 ID
        # 新交易: entry_long 价格与前一行不同（包括从 NaN 变为有值，或值发生变化）
        df = df.with_columns(
            [
                (
                    # 前一行无值但当前有值
                    (
                        pl.col("entry_long_price").shift(1).is_nan()
                        & pl.col("entry_long_price").is_not_nan()
                    )
                    # 或者价格发生变化
                    | (
                        pl.col("entry_long_price")
                        != pl.col("entry_long_price").shift(1)
                    )
                )
                .fill_null(True)
                .alias("is_new_long_trade"),
            ]
        ).with_columns(pl.col("is_new_long_trade").cum_sum().alias("long_trade_id"))

        # 只看有持仓且无离场（持仓中）且有 SL 价格的行
        df = df.filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_nan()
            & pl.col("sl_atr_price_long").is_not_nan()
        )

        if len(df) == 0:
            pytest.skip("无多头持仓且有 SL 价格的记录")

        # 按交易 ID 分组，检查每组内 SL 价格是否一致
        grouped = (
            df.group_by("long_trade_id")
            .agg(
                [
                    pl.col("sl_atr_price_long").min().alias("sl_min"),
                    pl.col("sl_atr_price_long").max().alias("sl_max"),
                    pl.len().alias("bar_count"),
                ]
            )
            .with_columns(
                (pl.col("sl_max") - pl.col("sl_min")).abs().alias("sl_spread")
            )
        )

        tolerance = 1e-10
        errors = grouped.filter(pl.col("sl_spread") > tolerance)

        if len(errors) > 0:
            print("\n❌ 同一交易内 SL 价格不一致:")
            print(errors.head(5))
            pytest.fail(f"发现 {len(errors)} 笔交易内 SL 价格变化")

        print(f"✅ {len(grouped)} 笔多头交易的 SL 价格保持不变")

    def test_tsl_atr_price_only_improves_in_same_trade(self, backtest_with_config):
        """验证 TSL ATR 价格在同一笔交易期间只向有利方向移动"""
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        if backtest_params.tsl_atr is None or backtest_params.tsl_atr.value == 0:
            pytest.skip("策略未启用 tsl_atr")

        df = results[0].backtest_result

        if "tsl_atr_price_long" not in df.columns:
            pytest.skip("回测结果无 tsl_atr_price_long 列")

        # 给每笔多头交易分配唯一 ID
        # 新交易: entry_long 价格与前一行不同
        df = df.with_columns(
            [
                (
                    (
                        pl.col("entry_long_price").shift(1).is_nan()
                        & pl.col("entry_long_price").is_not_nan()
                    )
                    | (
                        pl.col("entry_long_price")
                        != pl.col("entry_long_price").shift(1)
                    )
                )
                .fill_null(True)
                .alias("is_new_long_trade"),
                pl.col("tsl_atr_price_long").shift(1).alias("prev_tsl"),
            ]
        ).with_columns(pl.col("is_new_long_trade").cum_sum().alias("long_trade_id"))

        # 只看持仓期间，且非首次进场，且前后都有 TSL 价格的行
        df = df.filter(
            pl.col("entry_long_price").is_not_nan()
            & pl.col("exit_long_price").is_nan()
            & ~pl.col("is_new_long_trade")  # 非首次进场
            & pl.col("tsl_atr_price_long").is_not_nan()
            & pl.col("prev_tsl").is_not_nan()
        ).with_columns(
            (pl.col("tsl_atr_price_long") - pl.col("prev_tsl")).alias("tsl_change")
        )

        if len(df) == 0:
            pytest.skip("无连续持仓且有 TSL 价格的记录")

        # 多头 TSL 只能升不能降（允许微小浮点误差）
        errors = df.filter(pl.col("tsl_change") < -1e-10)

        if len(errors) > 0:
            print("\n❌ 同一交易内 TSL 价格下降 (前5条):")
            print(
                errors.select(
                    ["long_trade_id", "tsl_atr_price_long", "prev_tsl", "tsl_change"]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 TSL 价格异常下降")

        print(f"✅ {len(df)} 行持仓期间 TSL 价格保持只升不降")
