import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner
    from .params import SetupConfig

from py_entry.types import (
    SingleParamSet,
    TemplateContainer,
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
    runner: "BacktestRunner",
    config: "SetupConfig",
) -> None:
    """
    一次性配置回测所需的所有组件。
    """
    # 赋值计时开关
    runner.enable_timing = config.enable_timing

    start_time = time.perf_counter() if runner.enable_timing else None

    # 配置数据
    runner.data_dict = build_data(
        data_source=config.data_source,
        other_params=config.other_params,
    )

    if runner.data_dict is None:
        raise ValueError("data_dict 不能为空")

    # 直接创建单个 SingleParamSet
    runner.param_set = [
        SingleParamSet(
            indicators=build_indicators_params(config.indicators),
            signal=build_signal_params(config.signal),
            backtest=build_backtest_params(config.backtest),
            performance=build_performance_params(config.performance),
        )
        for _ in range(config.param_set_size)
    ]

    # 配置模板
    runner.template_config = TemplateContainer(
        signal=build_signal_template(config.signal_template),
    )

    # 配置引擎设置
    runner.engine_settings = build_engine_settings(config.engine_settings)

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.setup() 耗时: {elapsed:.4f}秒")
