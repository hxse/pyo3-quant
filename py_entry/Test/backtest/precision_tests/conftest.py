"""
精细化测试的 pytest 配置

复用 common_tests 的策略参数化机制
"""

import pytest

from py_entry.runner import BacktestRunner, SetupConfig
from py_entry.Test.backtest.strategies import get_all_strategies
from py_entry.Test.backtest.strategies.base import StrategyConfig


def _run_backtest(strategy: StrategyConfig):
    """执行回测并返回结果和原始数据"""
    br = BacktestRunner()

    br.setup(
        SetupConfig(
            data_source=strategy.data_config,
            indicators=strategy.indicators_params,
            signal=strategy.signal_params,
            backtest=strategy.backtest_params,
            signal_template=strategy.signal_template,
            engine_settings=strategy.engine_settings,
            performance=strategy.performance_params,
        )
    )

    br.run()
    return br.results, strategy, br.data_dict


@pytest.fixture(scope="class", params=get_all_strategies(), ids=lambda s: s.name)
def backtest_with_config(request):
    """
    参数化回测结果 fixture（包含策略配置和原始数据）

    返回 (results, strategy_config, data_dict) 元组
    """
    strategy: StrategyConfig = request.param
    print(f"\n🔬 精细化测试策略: {strategy.name}")
    return _run_backtest(strategy)


@pytest.fixture
def backtest_df(backtest_with_config):
    """从回测结果中提取 DataFrame，并添加 close 价格列"""
    results, strategy, data_dict = backtest_with_config
    if not results or not hasattr(results[0], "backtest_result"):
        return None

    df = results[0].backtest_result

    # 从 data_dict.source 中获取 close 价格并添加到 df
    if data_dict is not None:
        base_key = data_dict.base_data_key
        if base_key and base_key in data_dict.source:
            base_data = data_dict.source[base_key]
            if "close" in base_data.columns:
                close_series = base_data["close"]
                # 确保长度匹配
                if len(close_series) == len(df):
                    df = df.with_columns(close_series.alias("close"))

    return df


@pytest.fixture
def backtest_params(backtest_with_config):
    """获取回测参数"""
    _, strategy, _ = backtest_with_config
    return strategy.backtest_params
