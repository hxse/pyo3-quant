import time
from typing import Optional, List, Union
from types import SimpleNamespace
from loguru import logger

import pyo3_quant
from py_entry.types import (
    BacktestSummary,
    SingleParamSet,
    DataContainer,
    TemplateContainer,
    SettingContainer,
    OptimizerConfig,
    WalkForwardConfig,
    OptimizationResult,
    WalkForwardResult,
)


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


def _to_rust_param(param: SingleParamSet):
    """Convert SingleParamSet to a structure compatible with Rust engine.
    Rust expects attributes for the container, but PyDict for indicators/signal.
    """
    return SimpleNamespace(
        indicators=param.indicators.root,
        signal=param.signal.root,
        backtest=param.backtest,
        performance=param.performance,
    )


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

        # 直接调用 Rust 的单回测 API
        raw_result = pyo3_quant.backtest_engine.run_single_backtest(
            self.data_dict,
            _to_rust_param(target_params),
            self.template_config,
            self.engine_settings,
        )

        # 直接解析结果
        summary = BacktestSummary.model_validate(raw_result)

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
        """批量并发回测

        直接调用 run_backtest_engine(param_list)
        """
        start_time = time.perf_counter() if self.enable_timing else None

        raw_results = pyo3_quant.backtest_engine.run_backtest_engine(
            self.data_dict,
            [_to_rust_param(p) for p in param_list],
            self.template_config,
            self.engine_settings,
        )

        summaries = [BacktestSummary.model_validate(r) for r in raw_results]

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
            _to_rust_param(target_params),
            self.template_config,
            self.engine_settings,
            config,
        )

        result = OptimizeResult(OptimizationResult.model_validate(raw_result))

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.optimize() 耗时: {elapsed:.4f}秒")

        return result

    def walk_forward(
        self,
        config: Optional[WalkForwardConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> WalkForwardResultWrapper:
        """向前测试"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or WalkForwardConfig()
        target_params = params_override or self.params

        raw_result = pyo3_quant.backtest_engine.walk_forward.py_run_walk_forward(
            self.data_dict,
            _to_rust_param(target_params),
            self.template_config,
            self.engine_settings,
            config,
        )

        result = WalkForwardResultWrapper(
            WalkForwardResult.model_validate(raw_result),
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
