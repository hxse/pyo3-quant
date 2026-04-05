"""统一执行器：消费 CommonStrategySpec 协议。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.runner import Backtest
from py_entry.strategy_hub.core.config import (
    REQUIRED_SYMBOL_PLACEHOLDER,
    build_opt_cfg,
    build_sens_cfg,
    build_wf_cfg,
)
from py_entry.strategy_hub.core.spec import (
    CommonStrategySpec,
    SearchSpaceSpec,
)


def _override_symbol(
    spec: CommonStrategySpec, symbol: str | None
) -> CommonStrategySpec:
    """按需覆盖 symbol，保持 Spec 不可变。"""

    if symbol is None:
        return spec
    data_cfg = spec.data_config
    if not isinstance(data_cfg, OhlcvDataFetchConfig):
        return spec
    new_data_cfg = data_cfg.model_copy(update={"symbol": symbol})
    return replace(spec, data_config=new_data_cfg)


def build_backtest(spec: CommonStrategySpec, *, symbol: str | None = None) -> Backtest:
    """从统一协议构建 Backtest。"""

    effective = _override_symbol(spec, symbol)
    data_cfg = effective.data_config
    if isinstance(data_cfg, OhlcvDataFetchConfig) and (
        not data_cfg.symbol.strip()
        or data_cfg.symbol.strip() == REQUIRED_SYMBOL_PLACEHOLDER
    ):
        raise ValueError(
            "策略 data_config.symbol 未设置。请在调用阶段显式传入 --symbols。"
        )
    variant = effective.variant
    return Backtest(
        enable_timing=True,
        data_source=effective.data_config,
        indicators=variant.indicators_params,
        signal=variant.signal_params,
        backtest=variant.backtest_params,
        signal_template=variant.signal_template,
        engine_settings=effective.engine_settings,
        performance=effective.performance_params,
    )


def get_stage_configs(spec: CommonStrategySpec) -> dict[str, Any]:
    """读取阶段配置，无 research 时使用默认配置。"""

    if isinstance(spec, SearchSpaceSpec):
        return {
            "opt_cfg": spec.research.opt_cfg,
            "sens_cfg": spec.research.sens_cfg,
            "wf_cfg": spec.research.wf_cfg,
        }

    research = getattr(spec, "research", None)
    if research is None:
        return {
            "opt_cfg": build_opt_cfg(),
            "sens_cfg": build_sens_cfg(),
            "wf_cfg": build_wf_cfg(),
        }
    return {
        "opt_cfg": research.opt_cfg,
        "sens_cfg": research.sens_cfg,
        "wf_cfg": research.wf_cfg,
    }


def run_stage(
    spec: CommonStrategySpec,
    *,
    stage: str,
    symbol: str | None = None,
    bt: Backtest | None = None,
    stages: dict[str, Any] | None = None,
) -> Any:
    """执行单阶段。"""

    active_bt = bt or build_backtest(spec, symbol=symbol)
    # 中文注释：支持调用方传入已构建配置，避免重复构建与分支漂移。
    active_stages = stages or get_stage_configs(spec)

    if stage == "backtest":
        return active_bt.run()
    if stage == "optimize":
        return active_bt.optimize(active_stages["opt_cfg"])
    if stage == "sensitivity":
        return active_bt.sensitivity(active_stages["sens_cfg"])
    if stage == "walk_forward":
        wf_cfg = active_stages["wf_cfg"]
        active_bt.validate_wf_indicator_readiness(wf_cfg)
        return active_bt.walk_forward(wf_cfg)
    raise ValueError(f"不支持的阶段: {stage}")


__all__ = [
    "build_backtest",
    "get_stage_configs",
    "run_stage",
]
