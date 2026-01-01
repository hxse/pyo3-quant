import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner

from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
    SingleParamSet,
    TemplateContainer,
    SettingContainer,
)
from py_entry.data_generator import (
    OtherParams,
    DataSourceConfig,
)
from .setup_utils import (
    build_data,
    build_indicators_params,
    build_signal_params,
    build_backtest_params,
    build_performance_params,
    build_signal_template,
    build_engine_settings,
)


def perform_setup(
    self: "BacktestRunner",
    data_source: DataSourceConfig | None = None,
    other_params: OtherParams | None = None,
    indicators_params: IndicatorsParams | None = None,
    signal_params: SignalParams | None = None,
    backtest_params: BacktestParams | None = None,
    performance_params: PerformanceParams | None = None,
    signal_template: SignalTemplate | None = None,
    engine_settings: SettingContainer | None = None,
    param_set_size: int = 1,
) -> None:
    """
    一次性配置回测所需的所有组件。

    Args:
        self: BacktestRunner 实例，用于访问和修改状态。
        ... (其他参数与原 setup 方法一致)
    """
    start_time = time.perf_counter() if self.enable_timing else None

    # 配置数据
    self.data_dict = build_data(
        data_source=data_source,
        other_params=other_params,
    )

    if self.data_dict is None:
        raise ValueError("data_dict 不能为空")

    # 直接创建单个 SingleParamSet
    self.param_set = [
        SingleParamSet(
            indicators=build_indicators_params(indicators_params),
            signal=build_signal_params(signal_params),
            backtest=build_backtest_params(backtest_params),
            performance=build_performance_params(performance_params),
        )
        for _ in range(param_set_size)
    ]

    # 配置模板
    self.template_config = TemplateContainer(
        signal=build_signal_template(signal_template),
    )

    # 配置引擎设置
    self.engine_settings = build_engine_settings(engine_settings)

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.setup() 耗时: {elapsed:.4f}秒")
