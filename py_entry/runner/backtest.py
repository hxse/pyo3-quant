import time
import math
from typing import Optional, List, TYPE_CHECKING
from loguru import logger
import polars as pl

import pyo3_quant
from py_entry.types import (
    BacktestSummary,
    IndicatorContractReport,
    SingleParamSet,
    DataContainer,
    TemplateContainer,
    SettingContainer,
    ExecutionStage,
    OptimizerConfig,
    OptunaConfig,
    WalkForwardConfig,
    WfWarmupMode,
    OptimizationResult,
    WalkForwardResult,
    SensitivityConfig,
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
    Param,
    SignalTemplate,
)

# Results
from py_entry.runner.results.run_result import RunResult
from py_entry.runner.results.batch_result import BatchResult
from py_entry.runner.results.opt_result import OptimizeResult
from py_entry.runner.results.sens_result import SensitivityResultWrapper
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

    def resolve_indicator_contracts(
        self, params_override: Optional[SingleParamSet] = None
    ) -> IndicatorContractReport:
        """解析并返回指标契约聚合结果（Phase 1 入口）"""
        target_params = params_override or self.params
        return pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            target_params.indicators
        )

    @staticmethod
    def _is_missing(value: object) -> bool:
        """统一判空（None/NaN）。"""
        return value is None or (isinstance(value, float) and math.isnan(value))

    @staticmethod
    def _indicator_output_columns(indicators_df, indicator_key: str) -> list[str]:
        """按全列口径返回指标输出列。"""
        # 中文注释：全列口径要求对该指标实例全部输出列进行校验，禁止只挑主列。
        return [c for c in indicators_df.columns if c.startswith(indicator_key)]

    @staticmethod
    def _missing_expr(col_name: str) -> pl.Expr:
        """统一缺失表达式（null 或 NaN）。"""
        # 中文注释：先转浮点，确保 bool/int 列也能统一执行 is_nan 判定。
        col = pl.col(col_name).cast(pl.Float64, strict=False)
        return col.is_null() | col.is_nan()

    @classmethod
    def _leading_missing_count(cls, indicators_df, col: str) -> int:
        """计算单列前导空值数量（Polars 向量化）。"""
        missing_mask = (
            indicators_df.select(cls._missing_expr(col).alias("__missing"))
            .get_column("__missing")
            .cast(pl.Boolean, strict=False)
        )
        if missing_mask.len() == 0:
            return 0
        # 中文注释：全为空时前导空值数量等于列长度；否则首个 False 的索引就是前导空值数量。
        if bool(missing_mask.all()):
            return int(missing_mask.len())
        return int(missing_mask.arg_min())

    def validate_wf_indicator_readiness(
        self,
        wf_cfg: WalkForwardConfig,
        params_override: Optional[SingleParamSet] = None,
    ) -> dict:
        """WF 预检：契约聚合 + 指标运行时就绪校验（Fail-Fast）。"""
        target_params = params_override or self.params
        resolved_indicators = {}
        # 中文注释：预检参数统一按固定规则解析（optimize=true 取 max），并构造独立参数树。
        for source, source_map in target_params.indicators.items():
            resolved_indicators[source] = {}
            for indicator_key, indicator_map in source_map.items():
                resolved_indicators[source][indicator_key] = {}
                for param_name, param_obj in indicator_map.items():
                    resolved_value = (
                        param_obj.max
                        if bool(getattr(param_obj, "optimize", False))
                        and getattr(param_obj, "max", None) is not None
                        else param_obj.value
                    )
                    resolved_indicators[source][indicator_key][param_name] = Param(
                        value=resolved_value,
                        min=param_obj.min,
                        max=param_obj.max,
                        step=param_obj.step,
                        optimize=False,
                        dtype=param_obj.dtype,
                    )

        precheck_params = SingleParamSet(
            indicators=resolved_indicators,
            signal=target_params.signal,
            backtest=target_params.backtest,
            performance=target_params.performance,
        )

        report = self.resolve_indicator_contracts(precheck_params)

        base_data_key = self.data_dict.base_data_key
        # 中文注释：无指标策略允许通过，base 预热按 0 处理。
        if not report.warmup_bars_by_source:
            indicator_warmup_bars_base = 0
        elif base_data_key not in report.warmup_bars_by_source:
            raise ValueError(
                f"WF 预检失败：warmup_bars_by_source 缺少 base_data_key={base_data_key}"
            )
        else:
            indicator_warmup_bars_base = int(
                report.warmup_bars_by_source[base_data_key]
            )

        # 中文注释：WF 基础参数硬约束，直接报错，不做回退。
        if int(wf_cfg.transition_bars) < 1:
            raise ValueError("WF 预检失败：transition_bars 必须 >= 1")
        if int(wf_cfg.test_bars) < 2:
            raise ValueError("WF 预检失败：test_bars 必须 >= 2")

        effective_transition = max(int(wf_cfg.transition_bars), 1)
        if wf_cfg.wf_warmup_mode != WfWarmupMode.NoWarmup:
            effective_transition = max(effective_transition, indicator_warmup_bars_base)
        else:
            if indicator_warmup_bars_base > effective_transition:
                raise ValueError(
                    "WF 预检失败：NoWarmup 模式下 transition_bars 不足以承载指标预热需求 "
                    f"(required={indicator_warmup_bars_base}, transition={effective_transition})"
                )
        if (
            wf_cfg.wf_warmup_mode == WfWarmupMode.BorrowFromTrain
            and effective_transition > int(wf_cfg.train_bars)
        ):
            raise ValueError(
                "WF 预检失败：BorrowFromTrain 要求 "
                f"effective_transition_bars({effective_transition}) <= train_bars({wf_cfg.train_bars})"
            )

        indicator_settings = SettingContainer(
            execution_stage=ExecutionStage.Indicator,
            return_only_final=False,
        )
        indicator_summary = pyo3_quant.backtest_engine.run_single_backtest(
            self.data_dict,
            precheck_params,
            self.template_config,
            indicator_settings,
        )
        if indicator_summary.indicators is None:
            raise ValueError("WF 预检失败：Indicator 阶段未返回指标结果")

        for instance_key, contract in report.contracts_by_indicator.items():
            source = contract.source
            warmup = int(contract.warmup_bars)
            mode = str(contract.warmup_mode)
            indicator_key = instance_key.split("::", 1)[1]

            if source not in indicator_summary.indicators:
                raise ValueError(
                    f"WF 预检失败：指标结果缺少 source={source}（{instance_key}）"
                )
            source_df = indicator_summary.indicators[source]
            output_cols = self._indicator_output_columns(source_df, indicator_key)
            if not output_cols:
                raise ValueError(f"WF 预检失败：找不到指标输出列（{instance_key}）")

            rows = int(source_df.height)
            if warmup < 0 or warmup > rows:
                raise ValueError(
                    f"WF 预检失败：warmup 越界（{instance_key}, warmup={warmup}, rows={rows}）"
                )

            # 中文注释：全列口径下，warmup 必须等于“各列前导空值数量”的最大值。
            observed_warmup = max(
                self._leading_missing_count(source_df, col) for col in output_cols
            )
            if observed_warmup != warmup:
                raise ValueError(
                    "WF 预检失败：warmup 与全列口径不一致 "
                    f"（instance={instance_key}, source={source}, required={warmup}, observed={observed_warmup}）"
                )

            if warmup >= rows:
                continue

            data_slice = source_df.slice(warmup, rows - warmup)
            if mode == "Strict":
                # 中文注释：向量化检测各列是否存在缺失，失败时再定位首个问题单元用于报错。
                missing_counts_df = data_slice.select(
                    [self._missing_expr(col).sum().alias(col) for col in output_cols]
                )
                bad_cols = [
                    col
                    for col in output_cols
                    if int(missing_counts_df[col][0] or 0) > 0
                ]
                if bad_cols:
                    bad_col = bad_cols[0]
                    missing_mask = (
                        data_slice.select(
                            self._missing_expr(bad_col).alias("__missing")
                        )
                        .get_column("__missing")
                        .cast(pl.Boolean, strict=False)
                    )
                    # 中文注释：存在缺失时，arg_max 可定位第一个 True 位置用于诊断。
                    first_bad_row = int(missing_mask.arg_max())
                    raise ValueError(
                        "WF 预检失败：Strict 非预热段存在空值 "
                        f"（{instance_key}, row={warmup + first_bad_row}, col={bad_col}）"
                    )
            elif mode == "Relaxed":
                # 中文注释：Relaxed 允许结构性空值，但按行不能“整行全空”。
                row_all_missing = (
                    data_slice.select(
                        pl.all_horizontal(
                            [self._missing_expr(col) for col in output_cols]
                        ).alias("__row_all_missing")
                    )
                    .get_column("__row_all_missing")
                    .cast(pl.Boolean, strict=False)
                )
                if bool(row_all_missing.any()):
                    absolute_row = warmup + int(row_all_missing.arg_max())
                    raise ValueError(
                        "WF 预检失败：Relaxed 非预热段存在整行全空 "
                        f"（{instance_key}, row={absolute_row}）"
                    )
            else:
                raise ValueError(
                    f"WF 预检失败：未知 warmup_mode={mode}（{instance_key}）"
                )

        return {
            "base_data_key": base_data_key,
            "indicator_warmup_bars_base": indicator_warmup_bars_base,
            "effective_transition_bars": effective_transition,
            "warmup_bars_by_source": report.warmup_bars_by_source,
            "contracts_by_indicator": report.contracts_by_indicator,
        }

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
        config: WalkForwardConfig,
        params_override: Optional[SingleParamSet] = None,
    ) -> WalkForwardResultWrapper:
        """向前测试"""
        start_time = time.perf_counter() if self.enable_timing else None

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
    ) -> SensitivityResultWrapper:
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

        return SensitivityResultWrapper(raw_result)
