"""测试单 Bar 状态枚举白名单"""

import polars as pl


class TestStateWhitelist:
    """
    验证每一行的状态组合都在 11 种合法状态白名单中。

    白名单基于约束体系推导，详见 doc/backtest/state_machine_constraints.md
    """

    # 15 种合法状态白名单
    # 格式: (entry_long, exit_long, entry_short, exit_short, in_bar_direction, first_entry_side)
    # True = 有值, False = 无值 (NaN)
    VALID_STATES = [
        # #1 无仓位
        (False, False, False, False, 0, 0),  # no_position
        # #2 持有多头 (延续)
        (True, False, False, False, 0, 0),  # hold_long
        # #3 持有多头 (进场)
        (True, False, False, False, 0, 1),  # hold_long_first
        # #4 持有空头 (延续)
        (False, False, True, False, 0, 0),  # hold_short
        # #5 持有空头 (进场)
        (False, False, True, False, 0, -1),  # hold_short_first
        # #6 多头离场 (信号)
        (True, True, False, False, 0, 0),  # exit_long_signal
        # #7 多头离场 (持仓后风控)
        (True, True, False, False, 1, 0),  # exit_long_risk
        # #8 多头离场 (秒杀)
        (True, True, False, False, 1, 1),  # exit_long_risk_first
        # #9 空头离场 (信号)
        (False, False, True, True, 0, 0),  # exit_short_signal
        # #10 空头离场 (持仓后风控)
        (False, False, True, True, -1, 0),  # exit_short_risk
        # #11 空头离场 (秒杀)
        (False, False, True, True, -1, -1),  # exit_short_risk_first
        # #12 反手 L->S
        (True, True, True, False, 0, -1),  # reversal_L_to_S
        # #13 反手 S->L
        (True, False, True, True, 0, 1),  # reversal_S_to_L
        # #14 反手风控 -> L
        (True, True, True, True, 1, 1),  # reversal_to_L_risk
        # #15 反手风控 -> S
        (True, True, True, True, -1, -1),  # reversal_to_S_risk
    ]

    def test_all_states_in_whitelist(self, backtest_df):
        """验证所有行的状态组合都在白名单中（矢量化）"""
        # 检查是否存在价格为 NaN 但 first_entry_side != 0 的异常行
        # 这种情况不应该发生（已在 reset_position_on_skip 中修复）
        nan_entry_anomaly = backtest_df.filter(
            (pl.col("entry_long_price").is_nan() & (pl.col("first_entry_side") == 1))
            | (
                pl.col("entry_short_price").is_nan()
                & (pl.col("first_entry_side") == -1)
            )
        )

        # 将价格列转换为布尔值（有值 = True, NaN = False）
        # 同时保留原始行号以便追踪
        df = backtest_df.with_row_index("index").with_columns(
            [
                pl.col("entry_long_price").is_not_nan().alias("el"),
                pl.col("exit_long_price").is_not_nan().alias("xl"),
                pl.col("entry_short_price").is_not_nan().alias("es"),
                pl.col("exit_short_price").is_not_nan().alias("xs"),
                pl.col("risk_in_bar_direction").alias("dir"),
                pl.col("first_entry_side").alias("fes"),
            ]
        )

        # 如果存在异常行，先排除它们，看看剩下的合不合法
        # 但我们不会让测试通过，除非异常行为 0
        df_clean = df.filter(
            ~(
                (
                    pl.col("entry_long_price").is_nan()
                    & (pl.col("first_entry_side") == 1)
                )
                | (
                    pl.col("entry_short_price").is_nan()
                    & (pl.col("first_entry_side") == -1)
                )
            )
        )

        # 构建白名单过滤条件（使用 OR 连接所有合法状态）
        whitelist_condition = pl.lit(False)
        for el, xl, es, xs, dir_val, fes_val in self.VALID_STATES:
            state_condition = (
                (pl.col("el") == el)
                & (pl.col("xl") == xl)
                & (pl.col("es") == es)
                & (pl.col("xs") == xs)
                & (pl.col("dir") == dir_val)
                & (pl.col("fes") == fes_val)
            )
            whitelist_condition = whitelist_condition | state_condition

        # 找出不在白名单中的行 (使用清洗后的数据)
        invalid_rows = df_clean.filter(~whitelist_condition)

        if len(invalid_rows) > 0:
            print(f"\n❌ 发现 {len(invalid_rows)} 行非法状态组合。前 20 行:")
            # 打印详细信息，包括可能导致问题的 NaN 值
            print(
                invalid_rows.select(
                    [
                        "index",
                        "el",
                        "xl",
                        "es",
                        "xs",
                        "dir",
                        "fes",
                        "entry_long_price",
                        "exit_long_price",
                        "entry_short_price",
                        "exit_short_price",
                    ]
                ).head(20)
            )

            # 检查是否有 NaN 引起的 False
            # 如果价格列有值（Some）但值是 NaN，is_not_nan() 会返回 False
            # 我们可以通过查看这些列是否为 null 来区分 None 和 NaN (在 Polars 中通常都处理为 null，但在 Rust -> Python转换中可能保留 NaN)
            print("\n检查是否存在 NaN 值 (非 Null):")
            chk_nan = invalid_rows.select(
                [
                    pl.col("entry_long_price").is_nan().alias("el_is_nan"),
                    pl.col("entry_short_price").is_nan().alias("es_is_nan"),
                ]
            ).head(20)
            print(chk_nan)

        assert len(invalid_rows) == 0, f"发现 {len(invalid_rows)} 行状态不在白名单中"

        # 如果是因为 NaN 进场导致的异常，明确报错
        if len(nan_entry_anomaly) > 0:
            assert False, (
                f"发现 {len(nan_entry_anomaly)} 行 NaN 价格进场异常。请检查 Rust 代码是否已重新编译且包含 NaN 检查逻辑。"
            )

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
                pl.col("first_entry_side").alias("fes"),
            ]
        )

        state_names = [
            "no_position",
            "hold_long",
            "hold_long_first",
            "hold_short",
            "hold_short_first",
            "exit_long_signal",
            "exit_long_risk",
            "exit_long_risk_first",
            "exit_short_signal",
            "exit_short_risk",
            "exit_short_risk_first",
            "reversal_long_to_short",
            "reversal_short_to_long",
            "reversal_to_long_then_exit",
            "reversal_to_short_then_exit",
        ]

        print("\n📊 状态分布:")
        for i, (el, xl, es, xs, dir_val, fes_val) in enumerate(self.VALID_STATES):
            count = len(
                df.filter(
                    (pl.col("el") == el)
                    & (pl.col("xl") == xl)
                    & (pl.col("es") == es)
                    & (pl.col("xs") == xs)
                    & (pl.col("dir") == dir_val)
                    & (pl.col("fes") == fes_val)
                )
            )
            if count > 0:
                print(f"  - {state_names[i]}: {count} 行")
