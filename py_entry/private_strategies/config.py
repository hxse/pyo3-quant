"""
private_strategies 通用配置构建器。

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
    OptimizeMetric,
    OptimizerConfig,
    SensitivityConfig,
    WalkForwardConfig,
)

# 中文注释：统一默认实时数据源配置，策略文件按需覆盖差异项。
DEFAULT_FETCH_CONFIG: dict[str, Any] = {
    "exchange_name": "binance",
    "market": "future",
    "since": "2024-01-01 00:00:00",
    "limit": 30000,
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
    "train_bars": 9000,
    "transition_bars": 3000,
    "test_bars": 3600,
}


def _apply_object_overrides(obj: object, overrides: dict[str, Any] | None) -> object:
    """将覆盖参数写入配置对象。"""
    if not overrides:
        return obj
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


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
        enable_cache=bool(final["enable_cache"]),
        mode=mode,
        base_data_key=base_data_key,
    )


def build_runtime_data_meta(
    *,
    symbol: str,
    timeframes: list[str],
    base_data_key: str,
    strategy_logic: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, object]:
    """构建运行时摘要里的数据源元信息，确保与真实数据请求同口径。"""
    final = dict(DEFAULT_FETCH_CONFIG)
    if overrides:
        final.update(overrides)
    return {
        "symbol": symbol,
        "base_data_key": base_data_key,
        "mode": str(final["mode"]),
        "since": _normalize_since_ms(final["since"]),
        "limit": int(final["limit"]),
        "timeframes": timeframes,
        "strategy_logic": strategy_logic,
    }


def build_opt_cfg(overrides: dict[str, Any] | None = None) -> OptimizerConfig:
    """构建统一优化配置。"""
    cfg = OptimizerConfig(**DEFAULT_OPT_CONFIG)
    return _apply_object_overrides(cfg, overrides)  # type: ignore[return-value]


def build_sens_cfg(overrides: dict[str, Any] | None = None) -> SensitivityConfig:
    """构建统一敏感性配置。"""
    cfg = SensitivityConfig(**DEFAULT_SENS_CONFIG)
    return _apply_object_overrides(cfg, overrides)  # type: ignore[return-value]


def build_wf_cfg(
    overrides: dict[str, Any] | None = None,
    *,
    opt_overrides: dict[str, Any] | None = None,
) -> WalkForwardConfig:
    """构建统一向前测试配置。"""
    cfg = WalkForwardConfig(
        train_bars=int(DEFAULT_WF_CONFIG["train_bars"]),
        transition_bars=int(DEFAULT_WF_CONFIG["transition_bars"]),
        test_bars=int(DEFAULT_WF_CONFIG["test_bars"]),
        optimizer_config=build_opt_cfg(opt_overrides),
    )
    return _apply_object_overrides(cfg, overrides)  # type: ignore[return-value]


def build_runtime_config(
    overrides: dict[str, Any] | None = None,
    *,
    wf_cfg: WalkForwardConfig | None = None,
    opt_cfg: OptimizerConfig | None = None,
) -> dict[str, object]:
    """构建统一运行时摘要配置。"""
    final_wf = wf_cfg or build_wf_cfg()
    final_opt = opt_cfg or build_opt_cfg()
    optimize_seed = int(final_opt.seed) if final_opt.seed is not None else GLOBAL_SEED
    runtime: dict[str, object] = {
        "optimize_metric": str(final_opt.optimize_metric),
        "optimize_seed": optimize_seed,
        "optimize_min_samples": int(final_opt.min_samples),
        "optimize_max_samples": int(final_opt.max_samples),
        "optimize_samples_per_round": int(final_opt.samples_per_round),
        "optimize_stop_patience": int(final_opt.stop_patience),
        "wf_train_bars": int(final_wf.train_bars),
        "wf_transition_bars": int(final_wf.transition_bars),
        "wf_test_bars": int(final_wf.test_bars),
    }
    if overrides:
        runtime.update(overrides)
    return runtime
