import pytest
import polars as pl


class TestFinancialLogic:
    """测试财务逻辑"""

    def test_no_negative_balance(self, backtest_df):
        """测试余额不为负"""
        min_balance = backtest_df["balance"].min()
        assert min_balance >= 0, f"发现负余额: {min_balance}"

        print(f"✅ 余额不为负 (最小值: {min_balance:.2f})")

    def test_no_negative_equity(self, backtest_df):
        """测试净值不为负"""
        min_equity = backtest_df["equity"].min()
        assert min_equity >= 0, f"发现负净值: {min_equity}"

        print(f"✅ 净值不为负 (最小值: {min_equity:.2f})")

    def test_peak_equity_monotonic(self, backtest_df):
        """测试峰值净值单调"""
        # 使用 Polars 矢量化操作检查峰值净值单调性
        monotonic_violations = (
            backtest_df.lazy()
            .with_columns([pl.col("peak_equity").shift(1).alias("prev_peak_equity")])
            .filter(pl.col("peak_equity") < pl.col("prev_peak_equity"))
            .select([pl.col("prev_peak_equity"), pl.col("peak_equity")])
            .collect()
        )

        assert len(monotonic_violations) == 0, (
            f"峰值净值不单调，发现{len(monotonic_violations)}个违规"
        )

        print("✅ 峰值净值单调")

    def test_financial_relationships(self, backtest_df):
        """测试财务数据关系"""
        # 基本统计信息
        initial_balance = backtest_df["balance"][0]
        final_balance = backtest_df["balance"][-1]
        initial_equity = backtest_df["equity"][0]
        final_equity = backtest_df["equity"][-1]

        # 使用 Polars 矢量化操作检查手续费单调递增
        fee_violations = (
            backtest_df.lazy()
            .with_columns([pl.col("fee_cum").shift(1).alias("prev_fee_cum")])
            .filter(pl.col("fee_cum") < pl.col("prev_fee_cum"))
            .select([pl.col("prev_fee_cum"), pl.col("fee_cum")])
            .collect()
        )

        assert len(fee_violations) == 0, (
            f"累计手续费不单调，发现{len(fee_violations)}个违规"
        )

        # 获取最终累计手续费
        final_fee_cum = backtest_df["fee_cum"][-1]

        print(f"📊 财务关系:")
        print(f"   初始余额: {initial_balance:.2f}")
        print(f"   最终余额: {final_balance:.2f}")
        print(f"   初始净值: {initial_equity:.2f}")
        print(f"   最终净值: {final_equity:.2f}")
        print(f"   总手续费: {final_fee_cum:.2f}")

        # 基本合理性检查
        assert final_balance > 0, "最终余额应该为正"
        assert final_equity > 0, "最终净值应该为正"

        print("✅ 财务关系合理")

    def test_balance_equity_relationship(self, backtest_df, hold_positions):
        """测试余额与净值关系：上一个仓位如果不是hold，那么当前的余额必然等于净值"""
        # 使用 Polars 矢量化操作
        # 创建延迟计算表达式
        lazy_df = backtest_df.lazy()

        # 获取上一个仓位（shift操作）
        df_with_prev = lazy_df.with_columns(
            pl.col("current_position").shift(1).alias("previous_position")
        ).filter(
            # 过滤掉第一行（没有上一个仓位）
            pl.col("previous_position").is_not_null()
        )

        # 识别非hold状态的行（HoldLong=2, HoldShort=-2）
        non_hold_mask = df_with_prev.filter(~pl.col("previous_position").is_in(hold_positions))

        # 计算余额和净值的差值
        violations_df = (
            non_hold_mask.with_columns(
                (pl.col("balance") - pl.col("equity"))
                .abs()
                .alias("balance_equity_diff")
            )
            .filter(
                # 找出差值大于容差的行
                pl.col("balance_equity_diff") > 1e-10
            )
            .collect()
        )

        # 统计信息
        total_checks = non_hold_mask.select(pl.len()).collect().item()
        violation_count = len(violations_df)

        print(f"📊 余额-净值关系检查:")
        print(f"   总检查次数: {total_checks}")
        print(f"   违规次数: {violation_count}")

        if violation_count > 0:
            print("⚠️  发现违规案例（前5个）:")
            # 使用 Polars 显示前5个违规案例，避免for循环
            violation_samples = violations_df.head(5)
            # 添加行号索引
            violation_samples_with_index = violation_samples.with_row_count("index")
            # 选择需要的列并格式化输出
            display_df = violation_samples_with_index.select(
                [
                    pl.col("index"),
                    pl.col("previous_position"),
                    pl.col("balance").round(6),
                    pl.col("equity").round(6),
                    pl.col("balance_equity_diff").round(2).alias("diff"),
                ]
            )
            print(display_df)

        # 断言：不应该有违规
        assert violation_count == 0, f"发现{violation_count}个余额-净值关系违规"

        print("✅ 余额-净值关系正确：非hold仓位后余额等于净值")
