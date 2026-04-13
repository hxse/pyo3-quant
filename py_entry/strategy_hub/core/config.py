"""
strategy_hub 通用配置构建器。

设计目标：
1. 统一优化/敏感性/WF/运行时摘要配置口径；
2. 支持策略级与搜索空间级按需覆盖；
3. 保持唯一入口，减少重复常量散落。
"""

from __future__ import annotations

from typing import Any, Literal, cast

from py_entry.constants import GLOBAL_SEED
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.io import load_local_config
from py_entry.types import (
    ArtifactRetention,
    ExecutionStage,
    OptimizeMetric,
    OptimizerConfig,
    PerformanceMetric,
    PerformanceParams,
    SettingContainer,
    SensitivityConfig,
    WalkForwardConfig,
    WfWarmupMode,
)

# 中文注释：搜索策略必须由调用方显式传入 symbol，策略文件内不允许写死真实品种名。
REQUIRED_SYMBOL_PLACEHOLDER = "__REQUIRED_SYMBOL__"

# 中文注释：统一默认实时数据源配置，策略文件按需覆盖差异项。
DEFAULT_FETCH_CONFIG: dict[str, Any] = {
    "exchange_name": "binance",
    "market": "future",
    "since": "2024-01-01 00:00:00",
    "limit": 30000,
    "end_backfill_min_step_bars": 5,
    "enable_cache": True,
    "mode": "live",
}

# 中文注释：统一默认优化配置（策略文件与搜索空间共用）。
DEFAULT_OPT_CONFIG: dict[str, Any] = {
    "min_samples": 350,
    "max_samples": 1200,
    "samples_per_round": 60,
    "stop_patience": 6,
    "optimize_metric": OptimizeMetric.CalmarRatioRaw,
    "seed": GLOBAL_SEED,
}

# 中文注释：统一默认敏感性配置。
DEFAULT_SENS_CONFIG: dict[str, Any] = {
    "jitter_ratio": 0.1,
    "n_samples": 40,
    "distribution": "normal",
    "metric": OptimizeMetric.CalmarRatioRaw,
    "seed": GLOBAL_SEED,
}

# 中文注释：统一默认 WF 窗口配置。
DEFAULT_WF_CONFIG: dict[str, Any] = {
    # 中文注释：全局默认窗口按研究主场景口径设置。
    "train_active_bars": 6000,
    "test_active_bars": 3000,
    "min_warmup_bars": 500,
    "warmup_mode": WfWarmupMode.ExtendTest,
}

# 中文注释：统一默认引擎设置（策略文件与搜索空间共用）。
DEFAULT_ENGINE_SETTINGS: dict[str, Any] = {
    "stop_stage": ExecutionStage.Performance,
    "artifact_retention": ArtifactRetention.AllCompletedStages,
}

# 中文注释：统一默认性能指标口径（Rust 端计算，Python 仅展示）。
DEFAULT_PERFORMANCE_METRICS: list[PerformanceMetric] = [
    PerformanceMetric.TotalReturn,
    PerformanceMetric.CalmarRatio,
    PerformanceMetric.CalmarRatioRaw,
    PerformanceMetric.SpanMs,
    PerformanceMetric.SpanDays,
    PerformanceMetric.TotalTrades,
    PerformanceMetric.AvgTradeIntervalMs,
    PerformanceMetric.AvgTradeIntervalDays,
    PerformanceMetric.AvgHoldingDurationMs,
    PerformanceMetric.MaxHoldingDurationMs,
    PerformanceMetric.AvgHoldingDurationDays,
    PerformanceMetric.AvgEmptyDurationMs,
    PerformanceMetric.MaxEmptyDurationMs,
    PerformanceMetric.MaxEmptyDurationDays,
    PerformanceMetric.MaxDrawdown,
]


def _normalize_since_ms(since: str | int) -> int:
    """统一将 since 转为毫秒时间戳。"""
    if isinstance(since, int):
        return since
    return get_utc_timestamp_ms(since)


def build_ohlcv_fetch_config(
    *,
    symbol: str,
    timeframes: list[str],
    base_data_key: str,
    overrides: dict[str, Any] | None = None,
) -> OhlcvDataFetchConfig:
    """构建统一 OhlcvDataFetchConfig，避免策略文件重复写数据源参数。"""
    final = dict(DEFAULT_FETCH_CONFIG)
    if overrides:
        final.update(overrides)
    exchange_name = str(final["exchange_name"])
    market = cast(Literal["future", "spot"], final["market"])
    mode = cast(Literal["sandbox", "live"], final["mode"])
    return OhlcvDataFetchConfig(
        config=load_local_config(),
        exchange_name=exchange_name,
        market=market,
        symbol=symbol,
        timeframes=timeframes,
        since=_normalize_since_ms(final["since"]),
        limit=int(final["limit"]),
        end_backfill_min_step_bars=int(final["end_backfill_min_step_bars"]),
        enable_cache=bool(final["enable_cache"]),
        mode=mode,
        base_data_key=base_data_key,
    )


def build_opt_cfg(overrides: dict[str, Any] | None = None) -> OptimizerConfig:
    """构建统一优化配置。"""
    final = dict(DEFAULT_OPT_CONFIG)
    if overrides:
        final.update(overrides)
    return OptimizerConfig(**final)


def build_sens_cfg(overrides: dict[str, Any] | None = None) -> SensitivityConfig:
    """构建统一敏感性配置。"""
    final = dict(DEFAULT_SENS_CONFIG)
    if overrides:
        final.update(overrides)
    return SensitivityConfig(**final)


def build_wf_cfg(
    overrides: dict[str, Any] | None = None,
    *,
    opt_overrides: dict[str, Any] | None = None,
) -> WalkForwardConfig:
    """构建统一向前测试配置。"""
    if overrides and "optimizer_config" in overrides and opt_overrides:
        raise ValueError(
            "build_wf_cfg 不允许同时传 overrides.optimizer_config 与 opt_overrides。"
        )
    final = dict(DEFAULT_WF_CONFIG)
    # 中文注释：先落默认优化配置，再统一 merge overrides，避免重复分支覆盖。
    final["optimizer_config"] = build_opt_cfg(opt_overrides)
    if overrides:
        final.update(overrides)

    optimizer_cfg = final.get("optimizer_config")
    if isinstance(optimizer_cfg, dict):
        final["optimizer_config"] = OptimizerConfig(**optimizer_cfg)
    elif optimizer_cfg is None:
        raise ValueError("walk_forward.optimizer_config 不能为空。")
    elif not isinstance(optimizer_cfg, OptimizerConfig):
        raise TypeError("walk_forward.optimizer_config 必须是 OptimizerConfig 或 dict")

    return WalkForwardConfig(**final)


def build_engine_settings(overrides: dict[str, Any] | None = None) -> SettingContainer:
    """构建统一引擎设置。"""
    final = dict(DEFAULT_ENGINE_SETTINGS)
    if overrides:
        final.update(overrides)
    return SettingContainer(**final)


def build_performance_params(
    overrides: dict[str, Any] | None = None,
) -> PerformanceParams:
    """构建统一性能参数。"""
    final: dict[str, Any] = {"metrics": list(DEFAULT_PERFORMANCE_METRICS)}
    if overrides:
        final.update(overrides)
    if final.get("metrics") is None:
        final["metrics"] = list(DEFAULT_PERFORMANCE_METRICS)
    return PerformanceParams(**final)
