"""
调试 NaN 进场价格问题 - 对比预处理前后的信号

关键问题：
- 信号阶段显示 row 9771 entry_short = false
- 但回测结果显示 row 9772 first_entry_side = -1（意味着 Rust 看到 prev_bar.entry_short = true）

假设：
- Python SIGNALS 阶段返回的是 **预处理前** 的信号
- Rust PreparedData 使用的是 **预处理后** 的信号

验证：
- 对比 Python 信号和回测中实际使用的值
"""

import polars as pl
from py_entry.runner import Backtest
from py_entry.Test.backtest.strategies.sma_crossover.pyo3 import get_config
from py_entry.types import SettingContainer, ExecutionStage
from typing import cast


def main():
    # 获取策略配置
    strategy = get_config()
    print(f"策略: {strategy.name}")

    # 运行完整回测
    bt = Backtest(
        data_source=strategy.data_config,
        indicators=strategy.indicators_params,
        signal=strategy.signal_params,
        backtest=strategy.backtest_params,
        signal_template=strategy.signal_template,
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.Backtest,
            return_only_final=False,
        ),
        performance=strategy.performance_params,
    )

    result = bt.run()

    # 获取回测结果和信号
    backtest_summary = result.results[0]
    backtest_df = backtest_summary.backtest_result
    signals_df = backtest_summary.signals  # 这是回测过程中实际使用的信号吗？

    if backtest_df is None:
        print("❌ 回测结果为空")
        return

    print(f"回测结果行数: {len(backtest_df)}")

    if signals_df is not None:
        print(f"信号数据行数: {len(signals_df)}")
        print(f"信号列: {signals_df.columns}")

        # 检查 row 9770-9775 的信号
        print("\n=== row 9770-9775 信号数据 ===")
        print(signals_df.slice(9770, 6))

        # 检查 row 9770-9775 的回测结果
        print("\n=== row 9770-9775 回测结果 ===")
        cols_to_show = [
            c
            for c in backtest_df.columns
            if "entry" in c or "exit" in c or "first" in c
        ]
        print(backtest_df.select(cols_to_show).slice(9770, 6))
    else:
        print("⚠️ signals_df 为空")

    # 找出异常行
    print("\n=== 异常诊断 ===")
    anomaly_df = backtest_df.with_row_index("idx").filter(
        (pl.col("entry_short_price").is_nan() & (pl.col("first_entry_side") == -1))
    )

    if anomaly_df.height > 0:
        first_idx = cast(int, anomaly_df["idx"].min())
        print(f"第一个异常行: {first_idx}")

        if signals_df is not None:
            # 检查 first_idx 和 first_idx-1 的信号
            print(f"\n信号 [{first_idx - 1}] (prev_bar):")
            print(signals_df.slice(first_idx - 1, 1))
            print(f"\n信号 [{first_idx}] (current_bar):")
            print(signals_df.slice(first_idx, 1))

            # 检查是否有 has_leading_nan
            if "has_leading_nan" in signals_df.columns:
                leading_nan_status = signals_df.slice(first_idx - 1, 2).select(
                    ["has_leading_nan"]
                )
                print(f"\nhas_leading_nan 状态:")
                print(leading_nan_status)

        # 打印回测结果中该行的所有列
        print(f"\n回测结果 [{first_idx}] 全部列:")
        print(backtest_df.slice(first_idx, 1))

        # 推测原因
        print("\n=== 推测原因 ===")
        print(
            "如果 signals_df[first_idx-1].entry_short == False，但 first_entry_side == -1，"
        )
        print("那么 PreparedData 中的 entry_short 与 signals_df 不一致。")
        print("可能原因：")
        print("1. signals_df 是预处理前的数据")
        print("2. PreparedData 使用了预处理后的数据")
        print("3. 预处理器改变了信号值")
    else:
        print("✅ 没有发现异常")


if __name__ == "__main__":
    main()
