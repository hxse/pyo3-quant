"""
状态机诊断工具

提供回测结果的状态机覆盖分析，帮助快速判断：
1. 是否覆盖全部 11 种状态
2. 各状态的分布情况
3. 缺失哪些状态
"""

from typing import TYPE_CHECKING
import polars as pl

if TYPE_CHECKING:
    from .results.run_result import RunResult
    from .params import DiagnoseStatesConfig

# 11 种合法状态白名单
# ... (保持不变)
VALID_STATES = [
    (False, False, False, False, 0, "no_position"),
    (True, False, False, False, 0, "hold_long"),
    (False, False, True, False, 0, "hold_short"),
    (True, True, False, False, 0, "exit_long_signal"),
    (True, True, False, False, 1, "exit_long_risk"),
    (False, False, True, True, 0, "exit_short_signal"),
    (False, False, True, True, -1, "exit_short_risk"),
    (True, True, True, False, 0, "reversal_long_to_short"),
    (True, False, True, True, 0, "reversal_short_to_long"),
    (True, True, True, True, 1, "reversal_to_long_then_exit"),
    (True, True, True, True, -1, "reversal_to_short_then_exit"),
]


def analyze_state_distribution(
    runner: "RunResult",
    config: "DiagnoseStatesConfig",
) -> dict:
    """
    分析回测结果的状态机分布。

    Args:
        runner: RunResult 实例
        config: DiagnoseStatesConfig
    """
    # RunResult 只包含一个 summary
    df = runner.summary.backtest_result
    if df is None:
        raise ValueError("回测结果不包含 backtest_result 数据")

    # 转换为布尔列
    df = df.with_columns(
        [
            pl.col("entry_long_price").is_not_nan().alias("el"),
            pl.col("exit_long_price").is_not_nan().alias("xl"),
            pl.col("entry_short_price").is_not_nan().alias("es"),
            pl.col("exit_short_price").is_not_nan().alias("xs"),
            pl.col("risk_in_bar_direction").alias("dir"),
        ]
    )

    # 统计各状态
    found_states = []
    missing_states = []
    distribution = {}

    for el, xl, es, xs, dir_val, name in VALID_STATES:
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
            found_states.append(name)
            distribution[name] = count
        else:
            missing_states.append(name)

    return {
        "found_states": found_states,
        "missing_states": missing_states,
        "distribution": distribution,
        "coverage": len(found_states) / 11,
        "is_complete": len(found_states) == 11,
    }


def perform_diagnose(
    runner: "RunResult",
    config: "DiagnoseStatesConfig",
) -> dict:
    """
    诊断回测结果的状态机覆盖情况。
    """
    if config.print_summary:
        result = analyze_state_distribution(runner, config)
        print(
            f"\n📊 状态机覆盖: {len(result['found_states'])}/11 ({result['coverage']:.0%})"
        )
        print("=" * 50)

        if result["is_complete"]:
            print("✅ 完整覆盖全部 11 种状态")
        else:
            print(f"⚠️ 缺失 {len(result['missing_states'])} 种状态:")
            for name in result["missing_states"]:
                print(f"   - {name}")

        print("\n📈 状态分布:")
        for name, count in sorted(result["distribution"].items(), key=lambda x: -x[1]):
            bar = "█" * min(count // 50, 20)  # 简单的条形图
            print(f"   {name:30s} {count:6d} {bar}")
        return result

    return analyze_state_distribution(runner, config)
