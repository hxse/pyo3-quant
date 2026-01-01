from py_entry.types import OptimizerConfig, OptimizationResult
from py_entry.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
)
import pyo3_quant

# 获取优化器执行函数
py_run_optimizer = pyo3_quant.backtest_engine.optimizer.py_run_optimizer  # type: ignore


class Optimizer:
    """参数优化器桥接类"""

    def __init__(
        self,
        data_dict: DataContainer,
        param_set: ParamContainer,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        config: OptimizerConfig | None = None,
    ):
        self.data_dict = data_dict
        self.param_set = param_set
        self.template_config = template_config
        self.engine_settings = engine_settings
        self.config = config or OptimizerConfig()

    def run(self) -> OptimizationResult:
        """执行优化"""
        # 注意：此处假设 py_run_optimizer 已经在 Rust 端正确注册并导出
        raw_result = py_run_optimizer(
            self.data_dict,
            self.param_set,
            self.template_config,
            self.engine_settings,
            self.config,
        )
        # Rust return value is typically a dict now (IntoPyObject) or object
        # OptimizationResult in Python is Pydantic model
        if isinstance(raw_result, dict):
            return OptimizationResult.model_validate(raw_result)
        # If it returns an object (e.g. PyClass), assume it has attributes or we convert
        # However, our Rust side returns Dict for OptimizationResult now.
        return OptimizationResult.model_validate(raw_result)
