import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner

import pyo3_quant
from py_entry.data_conversion.types import BacktestSummary
from py_entry.data_conversion.helpers import validate_no_none_fields


def perform_run(self: "BacktestRunner") -> None:
    """
    执行回测。

    Args:
        self: BacktestRunner 实例，用于访问和修改状态。
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.data_dict is None:
        raise ValueError("必须先调用 setup() 配置回测参数")
    if self.template_config is None:
        raise ValueError("必须先调用 setup() 配置回测参数")
    if self.engine_settings is None:
        raise ValueError("必须先调用 setup() 配置回测参数")
    if self.param_set is None:
        raise ValueError("必须先调用 setup() 配置回测参数")

    validate_no_none_fields(self.data_dict)
    validate_no_none_fields(self.template_config)
    validate_no_none_fields(self.engine_settings)

    # 验证 param_set 是列表类型
    if not isinstance(self.param_set, list):
        raise ValueError(
            f"param_set 应该是列表类型，但得到的是 {type(self.param_set).__name__}"
        )

    for i in self.param_set:
        validate_no_none_fields(i)

    raw_results = pyo3_quant.backtest_engine.run_backtest_engine(
        self.data_dict,
        self.param_set,
        self.template_config,
        self.engine_settings,
        None,
    )
    self.results = [BacktestSummary.from_dict(result) for result in raw_results]

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.run() 耗时: {elapsed:.4f}秒")
