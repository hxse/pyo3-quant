import pytest
from py_entry.types import ExecutionStage
from py_entry.strategy_hub.test_strategies import get_test_strategy
from py_entry.Test.shared import make_backtest_runner, make_engine_settings


@pytest.fixture
def base_backtest():
    """获取一个基础的策略配置"""
    strategy = get_test_strategy("reversal_extreme")
    return make_backtest_runner(
        data_source=strategy.data_config,
        indicators=strategy.variant.indicators_params,
        signal=strategy.variant.signal_params,
        backtest=strategy.variant.backtest_params,
        signal_template=strategy.variant.signal_template,
    )


def test_full_intermediate_results(base_backtest):
    """场景 1: 验证分阶段执行并保留所有中间结果 (return_only_final=False)"""
    # 1. 仅指标阶段
    base_backtest.engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Indicator, return_only_final=False
    )
    res = base_backtest.run()
    assert res.result.indicators is not None
    assert res.result.signals is None
    assert res.result.backtest_result is None
    assert res.result.performance is None

    # 2. 信号阶段
    base_backtest.engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Signals, return_only_final=False
    )
    res = base_backtest.run()
    assert res.result.indicators is not None
    assert res.result.signals is not None
    assert res.result.backtest_result is None

    # 3. 回测阶段
    base_backtest.engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Backtest, return_only_final=False
    )
    res = base_backtest.run()
    assert res.result.indicators is not None
    assert res.result.signals is not None
    assert res.result.backtest_result is not None
    assert res.result.performance is None


def test_memory_optimization_final_only(base_backtest):
    """场景 2: 验证内存优化模式 (return_only_final=True)"""
    # 1. 信号阶段 (只返回信号)
    base_backtest.engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Signals, return_only_final=True
    )
    res = base_backtest.run()
    assert res.result.indicators is None  # 应该被释放
    assert res.result.signals is not None
    assert res.result.backtest_result is None

    # 2. 回测阶段 (只返回回测结果)
    base_backtest.engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Backtest, return_only_final=True
    )
    res = base_backtest.run()
    assert res.result.signals is None  # 应该被释放
    assert res.result.backtest_result is not None
