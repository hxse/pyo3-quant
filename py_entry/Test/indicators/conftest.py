import pytest

from py_entry.data_generator import (
    DataGenerationParams,
)
from py_entry.types import (
    ExecutionStage,
    IndicatorsParams,
    DataContainer,
    BacktestSummary,
)
from py_entry.Test.shared import (
    TEST_START_TIME_MS,
    make_backtest_runner,
    make_engine_settings,
)


def run_indicator_backtest(
    data_params: DataGenerationParams,
    indicators_params: IndicatorsParams | dict,
) -> tuple[list[BacktestSummary], DataContainer]:
    """运行指标回测并返回结果和数据容器

    Args:
        data_params: 数据生成参数
        indicators_params: 指标参数

    Returns:
        (backtest_results, data_container) 元组
    """
    bt = make_backtest_runner(
        data_source=data_params,
        indicators=indicators_params,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Indicator,
            return_only_final=True,
        ),
    )
    result = bt.run()
    backtest_results = result.results
    data_container = result.data_dict

    if data_container is None:
        raise ValueError("data_container 不能为 None")
    if backtest_results is None:
        raise ValueError("backtest_results 不能为 None")

    return backtest_results, data_container


@pytest.fixture(scope="module")
def data_dict():
    """生成指标测试所需的测试数据"""
    timeframes = ["15m", "1h"]
    return DataGenerationParams(
        timeframes=timeframes,
        start_time=TEST_START_TIME_MS,
        num_bars=5000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )
