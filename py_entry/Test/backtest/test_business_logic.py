import pytest
import polars as pl


class TestBusinessLogic:
    """测试业务逻辑"""

    def test_position_transitions(self, backtest_df):
        """测试仓位转换（基于白名单，矢量化实现）"""
        # 统计仓位状态分布
        position_counts = (
            backtest_df.lazy()
            .group_by("current_position")
            .len()
            .sort("current_position")
            .collect()
        )

        print(f"📊 仓位状态分布: {position_counts.head(8).to_dict(as_series=False)}")

        # 使用 Polars 矢量化方式验证所有仓位转换
        transitions_df = (
            backtest_df.lazy()
            .with_columns([pl.col("current_position").shift(1).alias("prev_position")])
            .filter(pl.col("prev_position").is_not_null())
            .with_columns(
                [
                    # 使用 when-then 链构建白名单验证逻辑
                    pl.when(pl.col("prev_position") == 0)
                    .then(pl.col("current_position").is_in([0, 1, -1]))
                    .when(pl.col("prev_position") == 1)
                    .then(pl.col("current_position").is_in([2]))
                    .when(pl.col("prev_position") == 2)
                    .then(pl.col("current_position").is_in([2, 3, -4]))
                    .when(pl.col("prev_position") == 3)
                    .then(pl.col("current_position").is_in([0, 1, -1]))
                    .when(pl.col("prev_position") == 4)
                    .then(pl.col("current_position").is_in([2, -4]))
                    .when(pl.col("prev_position") == -1)
                    .then(pl.col("current_position").is_in([-2]))
                    .when(pl.col("prev_position") == -2)
                    .then(pl.col("current_position").is_in([-2, -3, 4]))
                    .when(pl.col("prev_position") == -3)
                    .then(pl.col("current_position").is_in([0, 1, -1]))
                    .when(pl.col("prev_position") == -4)
                    .then(pl.col("current_position").is_in([-2, 4]))
                    .otherwise(False)
                    .alias("is_valid")
                ]
            )
            .collect()
        )

        # 统计非法转换
        invalid_df = transitions_df.filter(~pl.col("is_valid"))

        if len(invalid_df) > 0:
            # 使用矢量化方式统计非法转换类型
            invalid_counts = (
                invalid_df.lazy()
                .with_columns(
                    [
                        (
                            pl.col("prev_position").cast(pl.Utf8)
                            + "→"
                            + pl.col("current_position").cast(pl.Utf8)
                        ).alias("transition")
                    ]
                )
                .group_by("transition")
                .len()
                .sort("len", descending=True)
                .collect()
            )

            print(f"❌ 发现 {len(invalid_df)} 个非法仓位转换:")
            for row in invalid_counts.iter_rows(named=True):
                print(f"  {row['transition']}: {row['len']} 次")

            assert False, f"存在非法仓位转换，详见上方统计"

        print(f"✅ 所有 {len(transitions_df)} 个仓位转换均合法")
