"""
精细化测试的 pytest 配置

复用 common_tests 的策略参数化机制
"""

import pytest

from py_entry.strategies import get_all_strategies
from py_entry.strategies.base import StrategyConfig
from py_entry.Test.shared import (
    extract_backtest_df_with_close,
    run_strategy_backtest,
)


@pytest.fixture(scope="class", params=get_all_strategies(), ids=lambda s: s.name)
def backtest_with_config(request):
    """
    参数化回测结果 fixture（包含策略配置和原始数据）

    返回 (results, strategy_config, data_dict) 元组
    """
    strategy: StrategyConfig = request.param
    return run_strategy_backtest(strategy)


@pytest.fixture
def backtest_df(backtest_with_config):
    """从回测结果中提取 DataFrame，并添加 close 价格列"""
    results, _, data_dict = backtest_with_config
    return extract_backtest_df_with_close(results, data_dict)


@pytest.fixture
def backtest_params(backtest_with_config):
    """获取回测参数"""
    _, strategy, _ = backtest_with_config
    return strategy.backtest_params
