import time
from typing import Optional, List
from loguru import logger

import pyo3_quant
from py_entry.types import (
    ArtifactRetention,
    ExecutionStage,
    SingleParamSet,
    DataPack,
    TemplateContainer,
    SettingContainer,
    OptimizerConfig,
    OptunaConfig,
    WalkForwardConfig,
    SensitivityConfig,
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

from py_entry.runner.results import (
    BatchBacktestView,
    OptimizationView,
    OptunaOptimizationView,
    RunnerSession,
    SensitivityView,
    SingleBacktestView,
    WalkForwardView,
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
        self.data_pack: DataPack = build_data(
            data_source=data_source,
            other_params=other_params,
        )

        if self.data_pack is None:
            raise ValueError("data_pack 不能为空")

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

    @property
    def session(self) -> RunnerSession:
        """返回正式共享运行上下文。"""
        return self._session_for(self.engine_settings)

    def _copy_engine_settings(
        self,
        engine_settings: SettingContainer,
    ) -> SettingContainer:
        """复制执行设置，避免结果 view 被后续 mutation 污染。"""
        return SettingContainer(
            stop_stage=engine_settings.stop_stage,
            artifact_retention=engine_settings.artifact_retention,
        )

    def _session_for(self, engine_settings: SettingContainer) -> RunnerSession:
        """返回指定执行设置对应的正式共享运行上下文。"""
        return RunnerSession(
            data_pack=self.data_pack,
            template_config=self.template_config,
            engine_settings=self._copy_engine_settings(engine_settings),
            enable_timing=self.enable_timing,
        )

    def _mode_engine_settings(
        self,
        artifact_retention: ArtifactRetention,
    ) -> SettingContainer:
        """构建模式入口固定要求的执行设置。"""
        return SettingContainer(
            stop_stage=ExecutionStage.Performance,
            artifact_retention=artifact_retention,
        )

    def run(
        self, params_override: Optional[SingleParamSet] = None
    ) -> SingleBacktestView:
        """单个回测"""
        start_time = time.perf_counter() if self.enable_timing else None

        target_params = params_override or self.params
        engine_settings = self._copy_engine_settings(self.engine_settings)

        # 直接调用 Rust 的单回测 API, #[pyclass] 类型直接传过去
        result = pyo3_quant.backtest_engine.run_single_backtest(
            self.data_pack,
            target_params,
            self.template_config,
            engine_settings,
        )

        result_view = SingleBacktestView(
            raw=result,
            params=target_params,
            session=self._session_for(engine_settings),
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.run() 耗时: {elapsed:.4f}秒")

        return result_view

    def resolve_indicator_contracts(
        self, params_override: Optional[SingleParamSet] = None
    ):
        """解析并返回指标契约聚合结果（Phase 1 入口）"""
        target_params = params_override or self.params
        return pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            target_params.indicators
        )

    def batch(self, param_list: List[SingleParamSet]) -> BatchBacktestView:
        """批量并发回测"""
        start_time = time.perf_counter() if self.enable_timing else None
        engine_settings = self._copy_engine_settings(self.engine_settings)

        results = pyo3_quant.backtest_engine.run_batch_backtest(
            self.data_pack,
            param_list,
            self.template_config,
            engine_settings,
        )

        session = self._session_for(engine_settings)
        batch_result = BatchBacktestView(
            items=[
                SingleBacktestView(raw=result, params=params, session=session)
                for result, params in zip(results, param_list)
            ],
            session=session,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"Backtest.batch() 耗时: {elapsed:.4f}秒 (tasks={len(param_list)})"
            )

        return batch_result

    def optimize(
        self,
        config: Optional[OptimizerConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> OptimizationView:
        """参数优化"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or OptimizerConfig()
        target_params = params_override or self.params
        engine_settings = self._mode_engine_settings(
            ArtifactRetention.StopStageOnly,
        )

        raw_result = pyo3_quant.backtest_engine.optimizer.py_run_optimizer(
            self.data_pack,
            target_params,
            self.template_config,
            engine_settings,
            config,
        )

        result = OptimizationView(
            raw=raw_result,
            session=self._session_for(engine_settings),
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.optimize() 耗时: {elapsed:.4f}秒")

        return result

    def optimize_with_optuna(
        self,
        config: Optional[OptunaConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> OptunaOptimizationView:
        """使用 Optuna 进行参数优化"""
        from py_entry.runner.optuna_optimizer import run_optuna_optimization

        config = config or OptunaConfig()
        return run_optuna_optimization(self, config, params_override)

    def walk_forward(
        self,
        config: WalkForwardConfig,
        params_override: Optional[SingleParamSet] = None,
    ) -> WalkForwardView:
        """向前测试"""
        start_time = time.perf_counter() if self.enable_timing else None

        target_params = params_override or self.params
        engine_settings = self._mode_engine_settings(
            ArtifactRetention.AllCompletedStages,
        )

        raw_result = pyo3_quant.backtest_engine.walk_forward.run_walk_forward(
            self.data_pack,
            target_params,
            self.template_config,
            engine_settings,
            config,
        )

        result = WalkForwardView(
            raw=raw_result,
            session=self._session_for(engine_settings),
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.walk_forward() 耗时: {elapsed:.4f}秒")

        return result

    def sensitivity(
        self,
        config: Optional[SensitivityConfig] = None,
        params_override: Optional[SingleParamSet] = None,
    ) -> SensitivityView:
        """参数敏感性分析 (Jitter Test)"""
        start_time = time.perf_counter() if self.enable_timing else None

        config = config or SensitivityConfig()
        target_params = params_override or self.params
        engine_settings = self._mode_engine_settings(
            ArtifactRetention.StopStageOnly,
        )

        # Rust 接口需对应 py_run_sensitivity_test
        raw_result = pyo3_quant.backtest_engine.sensitivity.run_sensitivity_test(
            self.data_pack,
            target_params,
            self.template_config,
            engine_settings,
            config,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Backtest.sensitivity() 耗时: {elapsed:.4f}秒")

        return SensitivityView(
            raw=raw_result,
            session=self._session_for(engine_settings),
        )
