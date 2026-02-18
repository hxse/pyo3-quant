"""
策略回测测试共享执行器。

统一 common_tests / precision_tests 的策略回测执行路径，
避免重复维护 Backtest 初始化与结果提取逻辑。
"""

from typing import Any

from py_entry.runner import Backtest
from py_entry.strategies.base import StrategyConfig


def run_strategy_backtest(
    strategy: StrategyConfig,
) -> tuple[list[Any], StrategyConfig, Any]:
    """执行单个策略回测，返回 (results, strategy, data_dict)。"""
    bt = Backtest(
        data_source=strategy.data_config,
        indicators=strategy.indicators_params,
        signal=strategy.signal_params,
        backtest=strategy.backtest_params,
        signal_template=strategy.signal_template,
        engine_settings=strategy.engine_settings,
        performance=strategy.performance_params,
    )
    result = bt.run()
    return result.results, strategy, result.data_dict


def extract_backtest_df_with_close(results: list[Any], data_dict: Any):
    """从 results 中提取回测 DataFrame，并在可用时补充 close 列。"""
    if not results or not hasattr(results[0], "backtest_result"):
        return None

    df = results[0].backtest_result

    # 从 base_data_key 对应源数据补充 close，便于精细化公式测试复用。
    if data_dict is not None:
        base_key = data_dict.base_data_key
        if base_key and base_key in data_dict.source:
            base_data = data_dict.source[base_key]
            if "close" in base_data.columns:
                close_series = base_data["close"]
                if len(close_series) == len(df):
                    df = df.with_columns(close_series.alias("close"))

    return df
