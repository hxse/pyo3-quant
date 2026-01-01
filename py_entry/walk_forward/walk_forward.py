from typing import Optional
from py_entry.types import WalkForwardConfig, WalkForwardResult
from py_entry.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
)
import pyo3_quant

# 获取 Rust 函数引用
try:
    py_run_walk_forward = pyo3_quant.backtest_engine.walk_forward.py_run_walk_forward  # type: ignore
except AttributeError:
    # 可能是还没编译或者路径不对，暂时忽略，运行时会报错
    print(
        "Warning: backtest_engine.walk_forward module not found. Rebuild Rust extension?"
    )
    py_run_walk_forward = None


class WalkForwardOptimizer:
    """向前滚动优化器"""

    def __init__(
        self,
        data_dict: DataContainer,
        param_set: ParamContainer,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        config: Optional[WalkForwardConfig] = None,
    ):
        self.data_dict = data_dict
        self.param_set = param_set
        self.template_config = template_config
        self.engine_settings = engine_settings
        self.config = config or WalkForwardConfig()

    def run(self) -> WalkForwardResult:
        """执行滚动优化"""
        if py_run_walk_forward is None:
            raise ImportError("backtest_engine.walk_forward module not available")

        # 将 WalkForwardConfig 传递给 Rust
        # Rust 的 FromPyObject 会处理结构转换
        raw_result = py_run_walk_forward(
            self.data_dict,
            self.param_set,
            self.template_config,
            self.engine_settings,
            self.config,
        )

        if isinstance(raw_result, dict):
            return WalkForwardResult.model_validate(raw_result)
        return WalkForwardResult.model_validate(raw_result)
