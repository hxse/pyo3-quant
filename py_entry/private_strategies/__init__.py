"""私有策略包（扁平化结构）。"""

from .template import (
    build_backtest,
    get_stage_configs,
    get_live_strategy,
    get_live_strategy_names,
    run_pipeline,
    run_stage,
)

__all__ = [
    "build_backtest",
    "get_stage_configs",
    "get_live_strategy",
    "get_live_strategy_names",
    "run_pipeline",
    "run_stage",
]
