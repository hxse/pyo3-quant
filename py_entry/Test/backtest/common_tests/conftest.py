"""
通用测试的 pytest 配置

使用策略注册表进行参数化测试，所有已注册策略都会被测试。
"""

import pytest

from py_entry.runner import BacktestRunner
from py_entry.Test.backtest.strategies import get_all_strategies
from py_entry.Test.backtest.strategies.base import StrategyConfig


def _run_backtest(strategy: StrategyConfig):
    """执行回测并返回结果"""
    br = BacktestRunner()

    br.setup(
        data_source=strategy.data_config,
        indicators_params=strategy.indicators_params,
        signal_params=strategy.signal_params,
        backtest_params=strategy.backtest_params,
        signal_template=strategy.signal_template,
        engine_settings=strategy.engine_settings,
        performance_params=strategy.performance_params,
    )

    br.run()
    return br.results


@pytest.fixture(scope="class", params=get_all_strategies(), ids=lambda s: s.name)
def backtest_result(request):
    """
    参数化回测结果 fixture

    对所有已注册策略执行回测，每个策略的测试独立运行。
    测试报告中会显示策略名称。
    """
    strategy: StrategyConfig = request.param
    print(f"\n🚀 正在测试策略: {strategy.name}")
    print(f"   {strategy.description}")
    return _run_backtest(strategy)


@pytest.fixture
def backtest_df(backtest_result):
    """从回测结果中提取DataFrame"""
    if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
        return None
    return backtest_result[0].backtest_result


@pytest.fixture
def current_strategy(request):
    """获取当前测试的策略配置"""
    # 从 backtest_result fixture 的参数中获取
    if hasattr(request, "param"):
        return request.param
    return None


# ============ 列定义 Fixtures ============


@pytest.fixture
def required_fixed_cols():
    """固定列定义（基于新的价格驱动架构）"""
    return [
        # 价格状态列
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
        # Risk 状态列 (新架构)
        "risk_exit_long_price",
        "risk_exit_short_price",
        "risk_in_bar_direction",  # i8 类型 (0, 1, -1)
        "first_entry_side",  # i8 类型 (0, 1, -1)
        # 资金状态列
        "balance",
        "equity",
        "current_drawdown",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
    ]


@pytest.fixture
def optional_cols():
    """可选列定义（基于output.rs源代码）"""
    return {
        "sl_pct_price_long": "百分比止损价格(多)",
        "sl_pct_price_short": "百分比止损价格(空)",
        "tp_pct_price_long": "百分比止盈价格(多)",
        "tp_pct_price_short": "百分比止盈价格(空)",
        "tsl_pct_price_long": "百分比跟踪止损价格(多)",
        "tsl_pct_price_short": "百分比跟踪止损价格(空)",
        "atr": "ATR指标值",
        "sl_atr_price_long": "ATR止损价格(多)",
        "sl_atr_price_short": "ATR止损价格(空)",
        "tp_atr_price_long": "ATR止盈价格(多)",
        "tp_atr_price_short": "ATR止盈价格(空)",
        "tsl_atr_price_long": "ATR跟踪止损价格(多)",
        "tsl_atr_price_short": "ATR跟踪止损价格(空)",
    }


@pytest.fixture
def financial_cols():
    """财务相关列定义"""
    return [
        "balance",
        "equity",
        "current_drawdown",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
    ]


@pytest.fixture
def price_cols():
    """价格相关列定义"""
    return [
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
    ]
