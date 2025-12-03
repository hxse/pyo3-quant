import pytest

from py_entry.data_conversion.data_generator import (
    DataGenerationParams,
)
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.types import (
    SettingContainer,
    ExecutionStage,
    IndicatorsParams,
    DataContainer,
    BacktestSummary,
)


def run_indicator_backtest(
    data_params: DataGenerationParams,
    indicators_params: IndicatorsParams,
) -> tuple[list[BacktestSummary], DataContainer]:
    """运行指标回测并返回结果和数据容器

    Args:
        data_params: 数据生成参数
        indicators_params: 指标参数

    Returns:
        (backtest_results, data_container) 元组
    """
    runner = BacktestRunner()
    runner.setup(
        data_source=data_params,
        indicators_params=indicators_params,
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.INDICATOR,
            return_only_final=True,
        ),
    )
    runner.run()
    backtest_results = runner.results
    data_container = runner.data_dict

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
        start_time=1735689600000,
        num_bars=5000,
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )
