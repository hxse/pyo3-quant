"""测试单 Bar 状态枚举白名单"""

import polars as pl


class TestStateWhitelist:
    """
    验证每一行的状态组合都在 11 种合法状态白名单中。

    白名单基于约束体系推导，详见 doc/backtest/state_machine_constraints.md
    """

    # 11 种合法状态白名单
    # 格式: (entry_long, exit_long, entry_short, exit_short, in_bar_direction)
    # True = 有值, False = 无值 (NaN)
    VALID_STATES = [
        # 基础状态
        (False, False, False, False, 0),  # no_position
        (True, False, False, False, 0),  # hold_long
        (False, False, True, False, 0),  # hold_short
        # 离场状态
        (True, True, False, False, 0),  # exit_long_signal
        (True, True, False, False, 1),  # exit_long_risk
        (False, False, True, True, 0),  # exit_short_signal
        (False, False, True, True, -1),  # exit_short_risk
        # 反手状态
        (True, True, True, False, 0),  # reversal_long_to_short
        (True, False, True, True, 0),  # reversal_short_to_long
        # 反手后 in-bar 离场
        (True, True, True, True, 1),  # reversal_to_long_then_exit
        (True, True, True, True, -1),  # reversal_to_short_then_exit
    ]

    def test_all_states_in_whitelist(self, backtest_df):
        """验证所有行的状态组合都在白名单中（矢量化）"""
        # 将价格列转换为布尔值（有值 = True, NaN = False）
        df = backtest_df.with_columns(
            [
                pl.col("entry_long_price").is_not_nan().alias("el"),
                pl.col("exit_long_price").is_not_nan().alias("xl"),
                pl.col("entry_short_price").is_not_nan().alias("es"),
                pl.col("exit_short_price").is_not_nan().alias("xs"),
                pl.col("risk_in_bar_direction").alias("dir"),
            ]
        )

        # 构建白名单过滤条件（使用 OR 连接所有合法状态）
        whitelist_condition = pl.lit(False)
        for el, xl, es, xs, dir_val in self.VALID_STATES:
            state_condition = (
                (pl.col("el") == el)
                & (pl.col("xl") == xl)
                & (pl.col("es") == es)
                & (pl.col("xs") == xs)
                & (pl.col("dir") == dir_val)
            )
            whitelist_condition = whitelist_condition | state_condition

        # 找出不在白名单中的行
        invalid_rows = df.filter(~whitelist_condition)

        if len(invalid_rows) > 0:
            print("\n❌ 发现非法状态组合:")
            print(
                invalid_rows.select(
                    [
                        "el",
                        "xl",
                        "es",
                        "xs",
                        "dir",
                        "entry_long_price",
                        "exit_long_price",
                        "entry_short_price",
                        "exit_short_price",
                        "risk_in_bar_direction",
                    ]
                ).head(10)
            )

        assert len(invalid_rows) == 0, f"发现 {len(invalid_rows)} 行状态不在白名单中"

        print(f"✅ 所有 {len(backtest_df)} 行状态均在白名单中")

    def test_state_distribution(self, backtest_df):
        """统计各状态分布（仅供参考，不做断言）"""
        df = backtest_df.with_columns(
            [
                pl.col("entry_long_price").is_not_nan().alias("el"),
                pl.col("exit_long_price").is_not_nan().alias("xl"),
                pl.col("entry_short_price").is_not_nan().alias("es"),
                pl.col("exit_short_price").is_not_nan().alias("xs"),
                pl.col("risk_in_bar_direction").alias("dir"),
            ]
        )

        state_names = [
            "no_position",
            "hold_long",
            "hold_short",
            "exit_long_signal",
            "exit_long_risk",
            "exit_short_signal",
            "exit_short_risk",
            "reversal_long_to_short",
            "reversal_short_to_long",
            "reversal_to_long_then_exit",
            "reversal_to_short_then_exit",
        ]

        print("\n📊 状态分布:")
        for i, (el, xl, es, xs, dir_val) in enumerate(self.VALID_STATES):
            count = len(
                df.filter(
                    (pl.col("el") == el)
                    & (pl.col("xl") == xl)
                    & (pl.col("es") == es)
                    & (pl.col("xs") == xs)
                    & (pl.col("dir") == dir_val)
                )
            )
            if count > 0:
                print(f"  - {state_names[i]}: {count} 行")
