"""测试单 Bar 状态枚举白名单"""

import polars as pl
import pyo3_quant


class TestStateWhitelist:
    """
    验证每一行的状态组合都在合法状态白名单中。

    通过价格字段组合可推断出 15 种通用持仓状态。
    第 16 种特殊状态 gap_blocked 的价格字段与 no_position 相同，
    通过 frame_state 列(值=15)区分，在 TestFrameStateCrossValidation 中验证。

    白名单基于约束体系推导，详见 doc/backtest/state_machine_constraints.md
    """

    # 15 种通过价格可推测的合法状态白名单
    # 格式: (entry_long, exit_long, entry_short, exit_short, in_bar_direction, first_entry_side)
    # True = 有值, False = 无值 (NaN)
    VALID_STATES = [
        # #1 无仓位
        (False, False, False, False, 0, 0),  # no_position / gap_blocked
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


class TestFrameStateCrossValidation:
    """
    验证 frame_state 列与价格字段推断结果的一致性。

    frame_state 是从价格字段推断的只读输出，此测试确保推断逻辑在 Rust 和 Python 端一致。
    """

    # frame_state 枚举值映射
    FRAME_STATE_MAP = {
        0: "no_position",
        1: "hold_long",
        2: "hold_long_first",
        3: "hold_short",
        4: "hold_short_first",
        5: "exit_long_signal",
        6: "exit_long_risk",
        7: "exit_long_risk_first",
        8: "exit_short_signal",
        9: "exit_short_risk",
        10: "exit_short_risk_first",
        11: "reversal_L_to_S",
        12: "reversal_S_to_L",
        13: "reversal_to_L_risk",
        14: "reversal_to_S_risk",
        15: "gap_blocked",
        16: "capital_exhausted",
    }

    def test_frame_state_column_exists(self, backtest_df):
        """验证 frame_state 列存在且类型正确"""
        assert "frame_state" in backtest_df.columns, "缺少 frame_state 列"
        assert backtest_df["frame_state"].dtype == pl.UInt8, (
            f"frame_state 类型应为 UInt8，实际为 {backtest_df['frame_state'].dtype}"
        )
        print("✅ frame_state 列存在且类型正确 (UInt8)")

    def test_frame_state_values_valid(self, backtest_df):
        """验证所有 frame_state 值都在合法范围内 (0-16)"""
        invalid = backtest_df.filter(
            (pl.col("frame_state") > 16) & (pl.col("frame_state") != 255)
        )
        if len(invalid) > 0:
            print(f"\n❌ 发现 {len(invalid)} 行非法 frame_state 值:")
            print(invalid.select(["frame_state"]).head(20))
        assert len(invalid) == 0, f"发现 {len(invalid)} 行非法 frame_state 值"
        print("✅ 所有 frame_state 值均在合法范围内")

    def test_frame_state_name_function(self, backtest_df):
        """验证 PyO3 导出的 frame_state_name 函数工作正常"""
        # 验证 frame_state_name 函数能正确解析所有出现的状态
        unique_states = backtest_df["frame_state"].unique().sort().to_list()
        for state_id in unique_states:
            # 统一使用 backtester 子模块中的唯一导出路径
            name = pyo3_quant.backtest_engine.backtester.frame_state_name(state_id)
            assert name != "invalid_state", (
                f"frame_state={state_id} 映射为 invalid_state"
            )
            expected = self.FRAME_STATE_MAP.get(state_id)
            if expected:
                assert name == expected, (
                    f"frame_state={state_id}: 期望 '{expected}', 实际 '{name}'"
                )

        print(f"✅ frame_state_name 函数验证通过，覆盖 {len(unique_states)} 种状态")

    def test_frame_state_cross_validation(self, backtest_df):
        """交叉验证：frame_state 列值与价格字段推断结果一致（矢量化）"""
        df = backtest_df.with_columns(
            [
                pl.col("entry_long_price").is_not_nan().alias("el"),
                pl.col("exit_long_price").is_not_nan().alias("xl"),
                pl.col("entry_short_price").is_not_nan().alias("es"),
                pl.col("exit_short_price").is_not_nan().alias("xs"),
            ]
        )

        # 排除 gap_blocked (15) 和 capital_exhausted (16)，它们的价格字段与 no_position 相同
        non_special = df.filter(~pl.col("frame_state").is_in([15, 16]))

        # 声明式映射表：(el, xl, es, xs, dir, fes) → expected_frame_state
        # 与文档 doc/backtest/backtest_architecture.md 中的 15 种状态完全对应
        STATE_RULES = [
            # el,    xl,    es,    xs,    dir, fes, state_id
            (False, False, False, False, 0, 0, 0),  # no_position
            (True, False, False, False, 0, 0, 1),  # hold_long
            (True, False, False, False, 0, 1, 2),  # hold_long_first
            (False, False, True, False, 0, 0, 3),  # hold_short
            (False, False, True, False, 0, -1, 4),  # hold_short_first
            (True, True, False, False, 0, 0, 5),  # exit_long_signal
            (True, True, False, False, 1, 0, 6),  # exit_long_risk
            (True, True, False, False, 1, 1, 7),  # exit_long_risk_first
            (False, False, True, True, 0, 0, 8),  # exit_short_signal
            (False, False, True, True, -1, 0, 9),  # exit_short_risk
            (False, False, True, True, -1, -1, 10),  # exit_short_risk_first
            (True, True, True, False, 0, -1, 11),  # reversal_L_to_S
            (True, False, True, True, 0, 1, 12),  # reversal_S_to_L
            (True, True, True, True, 1, 1, 13),  # reversal_to_L_risk
            (True, True, True, True, -1, -1, 14),  # reversal_to_S_risk
        ]

        # 数据驱动生成 when/then 链
        # 初始值为 255 (非法状态)
        expr = pl.lit(255, dtype=pl.UInt8)

        # 逆序遍历构建嵌套 when/then 链
        for el, xl, es, xs, dir_val, fes_val, state_id in reversed(STATE_RULES):
            cond = (
                (pl.col("el") == el)
                & (pl.col("xl") == xl)
                & (pl.col("es") == es)
                & (pl.col("xs") == xs)
                & (pl.col("risk_in_bar_direction") == dir_val)
                & (pl.col("first_entry_side") == fes_val)
            )
            expr = pl.when(cond).then(pl.lit(state_id, dtype=pl.UInt8)).otherwise(expr)

        result = non_special.with_columns(expr.alias("expected_frame_state"))

        # 一次性找出所有不匹配的行
        mismatched = result.filter(
            pl.col("frame_state") != pl.col("expected_frame_state")
        )

        if len(mismatched) > 0:
            print(f"\n❌ 发现 {len(mismatched)} 行 frame_state 不匹配:")
            print(
                mismatched.select(
                    [
                        "el",
                        "xl",
                        "es",
                        "xs",
                        "risk_in_bar_direction",
                        "first_entry_side",
                        "frame_state",
                        "expected_frame_state",
                    ]
                ).head(20)
            )

        assert len(mismatched) == 0, (
            f"发现 {len(mismatched)} 行 frame_state 与价格推断不一致"
        )
        print(f"✅ 交叉验证通过: {len(non_special)} 行 frame_state 与价格推断完全一致")

    def test_frame_state_distribution(self, backtest_df):
        """统计 frame_state 分布（仅供参考，不做断言）"""
        counts = backtest_df.group_by("frame_state").len().sort("frame_state")
        print("\n📊 frame_state 分布:")
        for row in counts.iter_rows():
            state_id, count = row
            name = self.FRAME_STATE_MAP.get(state_id, f"unknown({state_id})")
            print(f"  - [{state_id:2d}] {name}: {count} 行")
