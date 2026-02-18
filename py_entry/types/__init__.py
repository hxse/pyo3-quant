# 从 Rust 模块导入（#[pyclass] 类型）
from pyo3_quant import (
    Param,
    ParamType,
    BacktestParams,
    PerformanceMetric,
    PerformanceParams,
    SingleParamSet,
    DataContainer,
    OptimizerConfig,
    OptimizeMetric,
    BenchmarkFunction,
    SettingContainer,
    ExecutionStage,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    TemplateContainer,
    WalkForwardConfig,
    BacktestSummary,
    RoundSummary,
    SamplePoint,
    OptimizationResult,
    MetricDistributionStats,
    WindowResult,
    WalkForwardResult,
    SensitivityConfig,
    SensitivitySample,
    SensitivityResult,
)

# Python 类型别名（无 Rust 对应，保持向下兼容）
from typing import Dict, List
import polars as pl

SignalParams = Dict[str, Param]
IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
ParamContainer = List[SingleParamSet]
DataSource = Dict[str, pl.DataFrame]
PerformanceMetrics = Dict[str, float]
IndicatorResults = Dict[str, pl.DataFrame]

# 纯 Python 类型（保留）
from .chart_config import (
    ChartConfig,
    SeriesItemConfig,
    IndicatorLayoutItem,
    DashboardOverride,
    HorizontalLineOption,
    VerticalLineOption,
    CandleOption,
    HistogramOption,
    VolumeOption,
    LineOption,
    AreaOption,
    BaselineOption,
    BarOption,
)
from .inputs.optuna_config import OptunaConfig

__all__ = [
    "Param",
    "ParamType",
    "BacktestParams",
    "PerformanceMetric",
    "PerformanceParams",
    "SingleParamSet",
    "DataContainer",
    "OptimizerConfig",
    "OptimizeMetric",
    "BenchmarkFunction",
    "SettingContainer",
    "ExecutionStage",
    "LogicOp",
    "SignalGroup",
    "SignalTemplate",
    "TemplateContainer",
    "WalkForwardConfig",
    "BacktestSummary",
    "RoundSummary",
    "SamplePoint",
    "OptimizationResult",
    "MetricDistributionStats",
    "WindowResult",
    "WalkForwardResult",
    "SensitivityConfig",
    "SensitivitySample",
    "SensitivityResult",
    "SignalParams",
    "IndicatorsParams",
    "ParamContainer",
    "DataSource",
    "PerformanceMetrics",
    "IndicatorResults",
    "ChartConfig",
    "SeriesItemConfig",
    "IndicatorLayoutItem",
    "DashboardOverride",
    "HorizontalLineOption",
    "VerticalLineOption",
    "CandleOption",
    "HistogramOption",
    "VolumeOption",
    "LineOption",
    "AreaOption",
    "BaselineOption",
    "BarOption",
    "OptunaConfig",
]
