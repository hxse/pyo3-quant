import time
from typing import TYPE_CHECKING
from loguru import logger
from py_entry.optimizer.optimizer import Optimizer
from py_entry.types import OptimizerConfig

if TYPE_CHECKING:
    from .runner import BacktestRunner


def perform_optimize(
    runner: "BacktestRunner",
    config: OptimizerConfig | None,
):
    """
    执行参数优化逻辑处理。
    """
    start_time = time.perf_counter() if runner.enable_timing else None

    if runner.data_dict is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if runner.param_set is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if runner.template_config is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if runner.engine_settings is None:
        raise ValueError("必须先调用 setup() 配置参数")

    config = config or OptimizerConfig()

    optimizer = Optimizer(
        data_dict=runner.data_dict,
        param_set=runner.param_set,
        template_config=runner.template_config,
        engine_settings=runner.engine_settings,
        config=config,
    )
    result = optimizer.run()

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.optimize() 耗时: {elapsed:.4f}秒")

    return result
