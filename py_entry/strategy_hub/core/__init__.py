"""strategy_hub core 导出。"""

from .executor import build_backtest, get_stage_configs, run_stage
from .spec import (
    CommonStrategySpec,
    ResearchSpec,
    SearchSpaceSpec,
    StrategySpec,
    TestStrategySpec,
    VariantPayload,
)
from .spec_loader import (
    discover_modules,
    get_module_file,
    load_spec,
)

__all__ = [
    "CommonStrategySpec",
    "ResearchSpec",
    "SearchSpaceSpec",
    "StrategySpec",
    "TestStrategySpec",
    "VariantPayload",
    "build_backtest",
    "discover_modules",
    "get_module_file",
    "get_stage_configs",
    "load_spec",
    "run_stage",
]
