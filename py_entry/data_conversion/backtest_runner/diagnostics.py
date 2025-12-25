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
    from .runner import BacktestRunner

# 11 种合法状态白名单
# 格式: (entry_long, exit_long, entry_short, exit_short, in_bar_direction)
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


def analyze_state_distribution(runner: "BacktestRunner", result_index: int = 0) -> dict:
    """
    分析回测结果的状态机分布

    Args:
        runner: BacktestRunner 实例（已执行 run()）
        result_index: 回测结果索引（多参数集时使用）

    Returns:
        dict: 包含状态分布信息的字典，包括：
            - found_states: 找到的状态列表
            - missing_states: 缺失的状态列表
            - distribution: 各状态的计数
            - coverage: 覆盖比例 (found/11)
            - is_complete: 是否覆盖全部 11 种状态
    """
    if runner.results is None:
        raise ValueError("请先执行 run() 方法")

    if result_index >= len(runner.results):
        raise IndexError(
            f"结果索引 {result_index} 超出范围 (共 {len(runner.results)} 个)"
        )

    df = runner.results[result_index].backtest_result
    if df is None:
        raise ValueError(f"回测结果索引 {result_index} 不包含 backtest_result 数据")

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


def print_state_summary(runner: "BacktestRunner", result_index: int = 0) -> None:
    """
    打印状态机覆盖摘要

    Args:
        runner: BacktestRunner 实例
        result_index: 回测结果索引
    """
    result = analyze_state_distribution(runner, result_index)

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
