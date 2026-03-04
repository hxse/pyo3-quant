"""strategy_hub 统一策略协议定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from py_entry.data_generator import DataSourceConfig
from py_entry.types import (
    BacktestParams,
    OptimizerConfig,
    PerformanceParams,
    SensitivityConfig,
    SettingContainer,
    SignalTemplate,
    WalkForwardConfig,
)


@dataclass(frozen=True)
class VariantPayload:
    """单策略执行所需参数体。"""

    indicators_params: dict[str, dict[str, dict[str, Any]]]
    signal_params: dict[str, Any]
    backtest_params: BacktestParams
    signal_template: SignalTemplate


@dataclass(frozen=True)
class ResearchSpec:
    """研究阶段配置。"""

    opt_cfg: OptimizerConfig
    sens_cfg: SensitivityConfig
    wf_cfg: WalkForwardConfig


@dataclass(frozen=True)
class CommonStrategySpec:
    """统一策略最小交集。"""

    name: str
    version: str
    data_config: DataSourceConfig
    variant: VariantPayload
    engine_settings: SettingContainer
    performance_params: PerformanceParams | None
    chart_layout: Any | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class SearchSpaceSpec(CommonStrategySpec):
    """搜索空间策略协议。"""

    research: ResearchSpec
    source: Literal["search"] = "search"


@dataclass(frozen=True)
class TestStrategySpec(CommonStrategySpec):
    """测试策略协议。"""

    research: ResearchSpec | None = None
    source: Literal["test"] = "test"
    btp_strategy_class: Any | None = None
    custom_params: dict[str, Any] | None = None
    test_group: str | None = None


StrategySpec = SearchSpaceSpec | TestStrategySpec


def ensure_valid_spec(spec: CommonStrategySpec, *, module_name: str) -> None:
    """对外统一校验 Spec 合法性。"""

    if not spec.name.strip():
        raise ValueError(f"策略名不能为空: {module_name}")
    if not spec.version.strip():
        raise ValueError(f"策略版本不能为空: {module_name}")
    if not spec.data_config.base_data_key:
        raise ValueError(f"base_data_key 不能为空: {module_name}")
