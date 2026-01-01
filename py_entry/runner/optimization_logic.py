import time
from typing import Optional, TYPE_CHECKING
from loguru import logger
from py_entry.optimizer.optimizer import Optimizer
from py_entry.types import OptimizerConfig

if TYPE_CHECKING:
    from .runner import BacktestRunner
    from py_entry.types import WalkForwardConfig


def perform_optimize(
    self: "BacktestRunner",
    config: Optional[OptimizerConfig] = None,
):
    """
    执行参数优化逻辑处理。
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.data_dict is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.param_set is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.template_config is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.engine_settings is None:
        raise ValueError("必须先调用 setup() 配置参数")

    if config is None:
        config = OptimizerConfig()

    optimizer = Optimizer(
        data_dict=self.data_dict,
        param_set=self.param_set,
        template_config=self.template_config,
        engine_settings=self.engine_settings,
        config=config,
    )
    result = optimizer.run()

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.optimize() 耗时: {elapsed:.4f}秒")

    return result


def perform_walk_forward(
    self: "BacktestRunner",
    config: Optional["WalkForwardConfig"] = None,
):
    """
    执行向前滚动优化逻辑处理。
    """
    from py_entry.walk_forward.walk_forward import WalkForwardOptimizer
    from py_entry.types import WalkForwardConfig

    start_time = time.perf_counter() if self.enable_timing else None

    if self.data_dict is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.param_set is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.template_config is None:
        raise ValueError("必须先调用 setup() 配置参数")
    if self.engine_settings is None:
        raise ValueError("必须先调用 setup() 配置参数")

    if config is None:
        config = WalkForwardConfig()

    optimizer = WalkForwardOptimizer(
        data_dict=self.data_dict,
        param_set=self.param_set,
        template_config=self.template_config,
        engine_settings=self.engine_settings,
        config=config,
    )
    result = optimizer.run()

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.walk_forward() 耗时: {elapsed:.4f}秒")

    return result
