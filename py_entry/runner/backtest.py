import time
from typing import Optional, List, TYPE_CHECKING, Any
from loguru import logger

import pyo3_quant
from py_entry.types import (
    BacktestSummary,
    SingleParamSet,
    DataContainer,
    TemplateContainer,
    SettingContainer,
    OptimizerConfig,
    OptunaConfig,
    WalkForwardConfig,
    OptimizationResult,
    WalkForwardResult,
    SensitivityConfig,
    SensitivityResult,
)

from py_entry.runner.results.optuna_result import OptunaOptResult
from py_entry.data_generator import DataSourceConfig, OtherParams
from py_entry.runner.setup_utils import (
    build_data,
    build_indicators_params,
    build_signal_params,
    build_backtest_params,
    build_performance_params,
    build_signal_template,
    build_engine_settings,
)
from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
)

# Results
from py_entry.runner.results.run_result import RunResult
from py_entry.runner.results.batch_result import BatchResult
from py_entry.runner.results.opt_result import OptimizeResult
from py_entry.runner.results.wf_result import WalkForwardResultWrapper


class Backtest:
    """回测配置容器和执行入口"""

    def __init__(
        self,
        data_source: DataSourceConfig,
        other_params: Optional[OtherParams] = None,
        indicators: Optional[IndicatorsParams | dict] = None,
        signal: Optional[SignalParams | dict] = None,
        backtest: Optional[BacktestParams] = None,
        performance: Optional[PerformanceParams] = None,
        signal_template: Optional[SignalTemplate] = None,
        engine_settings: Optional[SettingContainer] = None,
        enable_timing: bool = False,
    ):
        """初始化时完成所有配置"""
        assert isinstance(data_source, DataSourceConfig), (
            "data_source must be DataSourceConfig"
        )
        self.enable_timing = enable_timing
        start_time = time.perf_counter() if enable_timing else None

        # 1. 配置数据
        self.data_dict: DataContainer = build_data(
            data_source=data_source,
            other_params=other_params,
        )

        if self.data_dict is None:
            raise ValueError("data_dict 不能为空")

        # 2. 配置参数 (单个)
        self.params: SingleParamSet = SingleParamSet(
            indicators=build_indicators_params(indicators),
            signal=build_signal_params(signal),
            backtest=build_backtest_params(backtest),
            performance=build_performance_params(performance),
        )

        # 3. 配置模板
        self.template_config: TemplateContainer = TemplateContainer(
            signal=build_signal_template(signal_template),
        )

        # 4. 配置引擎设置
        self.engine_settings: SettingContainer = build_engine_settings(engine_settings)

        if enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest initialized in {elapsed:.4f}s")

    def run(self, params_override: Optional[SingleParamSet] = None) -> RunResult:
        """单个回测"""
        start_time = time.perf_counter() if self.enable_timing else None

        target_params = params_override or self.params

        # 直接调用 Rust 的单回测 API, #[pyclass] 类型直接传过去
        summary = pyo3_quant.backtest_engine.run_single_backtest(
            self.data_dict,
            target_params,
            self.template_config,
            self.engine_settings,
        )

        result = RunResult(
            summary=summary,
            params=target_params,
            data_dict=self.data_dict,
            template_config=self.template_config,
            engine_settings=self.engine_settings,
            enable_timing=self.enable_timing,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.run() 耗时: {elapsed:.4f}秒")

        return result

    def batch(self, param_list: List[SingleParamSet]) -> BatchResult:
        """批量并发回测"""
        start_time = time.perf_counter() if self.enable_timing else None

        summaries = pyo3_quant.backtest_engine.run_backtest_engine(
            self.data_dict,
            param_list,
            self.template_config,
            self.engine_settings,
        )

        result = BatchResult(
            summaries=summaries,
            param_list=param_list,
            context={
                "data_dict": self.data_dict,
                "template_config": self.template_config,
                "engine_settings": self.engine_settings,
                "enable_timing": self.enable_timing,
            },
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"Backtest.batch() 耗时: {elapsed:.4f}秒 (tasks={len(param_list)})"
            )

        return result

    def optimize(
        self,
        config: Optional[OptimizerConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> OptimizeResult:
        """参数优化"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or OptimizerConfig()
        target_params = params_override or self.params

        raw_result = pyo3_quant.backtest_engine.optimizer.py_run_optimizer(
            self.data_dict,
            target_params,
            self.template_config,
            self.engine_settings,
            config,
        )

        result = OptimizeResult(raw_result)

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.optimize() 耗时: {elapsed:.4f}秒")

        return result

    def optimize_with_optuna(
        self,
        config: Optional[OptunaConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> OptunaOptResult:
        """使用 Optuna 进行参数优化"""
        from py_entry.runner.optuna_optimizer import run_optuna_optimization

        config = config or OptunaConfig()
        return run_optuna_optimization(self, config, params_override)

    def walk_forward(
        self,
        config: Optional[WalkForwardConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> WalkForwardResultWrapper:
        """向前测试"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or WalkForwardConfig()
        target_params = params_override or self.params

        raw_result = pyo3_quant.backtest_engine.walk_forward.run_walk_forward(
            self.data_dict,
            target_params,
            self.template_config,
            self.engine_settings,
            config,
        )

        result = WalkForwardResultWrapper(
            raw_result,
            context={
                "data_dict": self.data_dict,
                "template_config": self.template_config,
                "engine_settings": self.engine_settings,
                "enable_timing": self.enable_timing,
            },
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.walk_forward() 耗时: {elapsed:.4f}秒")

        return result

    def sensitivity(
        self,
        config: Optional[SensitivityConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> "SensitivityResult":
        """参数敏感性分析 (Jitter Test)"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or SensitivityConfig()
        target_params = params_override or self.params

        # Rust 接口需对应 py_run_sensitivity_test
        raw_result = pyo3_quant.backtest_engine.sensitivity.run_sensitivity_test(
            self.data_dict,
            target_params,
            self.template_config,
            self.engine_settings,
            config,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.sensitivity() 耗时: {elapsed:.4f}秒")

        return raw_result
