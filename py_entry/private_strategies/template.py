"""
private_strategies 通用执行模板。

职责：
1. 自动发现并加载 private 策略配置模块；
2. 统一提供 CLI / notebook 共用入口；
3. 统一执行 backtest -> optimize -> sensitivity -> walk_forward 管道。
"""

from __future__ import annotations

import argparse
import importlib
import time
from pathlib import Path
from types import ModuleType
from typing import Callable, Any

from py_entry.runner import (
    Backtest,
    LogLevel,
    format_pipeline_summary_for_ai,
    run_pipeline as runner_run_pipeline,
)
from py_entry.strategies.base import StrategyConfig

_EXCLUDE_MODULES = {
    "__init__",
    "base",
    "config",
    "template",
    "strategy_searcher",
}
_STRATEGY_PACKAGE = "py_entry.private_strategies"


def _discover_module_names() -> list[str]:
    """自动扫描 private_strategies 下可加载的策略模块。"""
    base_dir = Path(__file__).resolve().parent
    names: list[str] = []
    for py_file in sorted(base_dir.glob("*.py"), key=lambda p: p.name):
        module_name = py_file.stem
        if module_name in _EXCLUDE_MODULES or module_name.startswith("_"):
            continue
        names.append(module_name)
    return names


def _load_strategy_module(module_name: str) -> ModuleType:
    """按模块名加载策略模块。"""
    return importlib.import_module(f"{_STRATEGY_PACKAGE}.{module_name}")


def _build_runtime(module_name: str) -> dict[str, Any]:
    """构建策略运行时对象。"""
    module = _load_strategy_module(module_name)
    cfg = get_live_strategy(module_name)

    build_opt_cfg = _require_callable(module, "build_opt_cfg")
    build_sens_cfg = _require_callable(module, "build_sens_cfg")
    build_wf_cfg = _require_callable(module, "build_wf_cfg")

    bt = build_backtest(cfg)
    runtime: dict[str, Any] = {
        "module": module,
        "cfg": cfg,
        "bt": bt,
        "opt_cfg": build_opt_cfg(),
        "sens_cfg": build_sens_cfg(),
        "wf_cfg": build_wf_cfg(),
    }
    return runtime


def _require_callable(module: ModuleType, name: str) -> Callable:
    """强约束：策略模块必须提供约定函数。"""
    fn = getattr(module, name, None)
    if fn is None or not callable(fn):
        raise AttributeError(f"策略模块 '{module.__name__}' 缺少可调用函数: {name}")
    return fn


def get_live_strategy_names() -> list[str]:
    """返回可用策略模块名列表（按文件名排序）。"""
    names: list[str] = []
    for module_name in _discover_module_names():
        module = _load_strategy_module(module_name)
        get_live_config = _require_callable(module, "get_live_config")
        cfg = get_live_config()
        if not isinstance(cfg, StrategyConfig):
            raise TypeError(
                f"策略模块 '{module.__name__}' 的 get_live_config 返回类型非法: {type(cfg)}"
            )
        if cfg.live_meta is None:
            raise ValueError(
                f"策略模块 '{module.__name__}' 缺少 live_meta，无法用于 private live 链路"
            )
        names.append(module_name)
    return names


def _build_strategy_index() -> dict[str, StrategyConfig]:
    """构建策略索引：支持模块名与策略名双键访问。"""
    index: dict[str, StrategyConfig] = {}
    for module_name in _discover_module_names():
        module = _load_strategy_module(module_name)
        get_live_config = _require_callable(module, "get_live_config")
        cfg = get_live_config()
        if not isinstance(cfg, StrategyConfig):
            raise TypeError(
                f"策略模块 '{module.__name__}' 的 get_live_config 返回类型非法: {type(cfg)}"
            )
        if cfg.live_meta is None:
            raise ValueError(
                f"策略模块 '{module.__name__}' 缺少 live_meta，无法用于 private live 链路"
            )
        if module_name in index:
            raise ValueError(f"private 策略模块名重复: {module_name}")
        index[module_name] = cfg
        strategy_name = cfg.name
        if strategy_name in index and strategy_name != module_name:
            raise ValueError(f"private 策略名冲突: {strategy_name}")
        index[strategy_name] = cfg
    return index


def get_live_strategy(module_name: str) -> StrategyConfig:
    """按模块名或策略名获取 live 策略配置。"""
    index = _build_strategy_index()
    if module_name not in index:
        raise KeyError(
            f"未找到 private 策略: {module_name}，可选: {get_live_strategy_names()}"
        )
    return index[module_name]


def build_backtest(config: StrategyConfig) -> Backtest:
    """统一构建 Backtest，避免策略文件重复样板代码。"""
    cfg = config
    return Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
        performance=cfg.performance_params,
    )


def get_stage_configs(module_name: str) -> dict[str, Any]:
    """按策略名获取阶段配置对象。"""
    module = _load_strategy_module(module_name)
    build_opt_cfg = _require_callable(module, "build_opt_cfg")
    build_sens_cfg = _require_callable(module, "build_sens_cfg")
    build_wf_cfg = _require_callable(module, "build_wf_cfg")
    return {
        "opt_cfg": build_opt_cfg(),
        "sens_cfg": build_sens_cfg(),
        "wf_cfg": build_wf_cfg(),
    }


def run_pipeline(module_name: str) -> dict[str, object]:
    """运行指定策略模块的完整研究管道。"""
    runtime = _build_runtime(module_name)
    cfg = runtime["cfg"]
    bt = runtime["bt"]

    return runner_run_pipeline(
        base_data_key=cfg.data_config.base_data_key,
        bt=bt,
        opt_cfg=runtime["opt_cfg"],
        sens_cfg=runtime["sens_cfg"],
        wf_cfg=runtime["wf_cfg"],
    )


def run_stage(module_name: str, stage: str):
    """按阶段执行指定策略模块。"""
    runtime = _build_runtime(module_name)
    bt = runtime["bt"]
    if stage == "backtest":
        return bt.run()
    if stage == "optimize":
        return bt.optimize(runtime["opt_cfg"])
    if stage == "sensitivity":
        return bt.sensitivity(runtime["sens_cfg"])
    if stage == "walk_forward":
        return bt.walk_forward(runtime["wf_cfg"])
    raise ValueError(f"不支持的阶段: {stage}")


def _format_pipeline_for_ai(
    module_name: str, summary: dict[str, object], elapsed: float
) -> str:
    """统一输出给 AI 的结构化摘要。"""
    module = _load_strategy_module(module_name)
    build_runtime_config = getattr(module, "build_runtime_config", None)
    runtime_config = build_runtime_config() if callable(build_runtime_config) else None
    return format_pipeline_summary_for_ai(
        summary,
        elapsed_seconds=elapsed,
        runtime_config=runtime_config,
    )


def _default_strategy_name() -> str:
    """返回默认策略名（第一个可用模块）。"""
    names = _discover_module_names()
    if not names:
        raise ValueError("未发现任何 private 策略模块")
    return names[0]


def main():
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="private_strategies 通用执行模板")
    parser.add_argument(
        "--strategy",
        default=None,
        help="策略模块名（默认自动取第一个）",
    )
    parser.add_argument(
        "--mode",
        default="pipeline",
        choices=["pipeline", "backtest", "optimize", "sensitivity", "walk_forward"],
        help="执行模式",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="仅列出可用策略模块",
    )
    args = parser.parse_args()

    if args.list:
        print(get_live_strategy_names())
        return

    strategy_name = args.strategy or _default_strategy_name()
    if strategy_name not in _discover_module_names():
        raise ValueError(
            f"未知策略模块: {strategy_name}，可选: {_discover_module_names()}"
        )

    start = time.perf_counter()
    if args.mode == "pipeline":
        summary = run_pipeline(strategy_name)
        elapsed = time.perf_counter() - start
        print(_format_pipeline_for_ai(strategy_name, summary, elapsed))
        return

    result = run_stage(strategy_name, args.mode)
    elapsed = time.perf_counter() - start
    print(f"strategy={strategy_name}, stage={args.mode}, elapsed_seconds={elapsed:.4f}")
    # 中文注释：优先打印结构化摘要，避免只显示对象地址影响审阅效率。
    if hasattr(result, "log") and callable(getattr(result, "log")):
        result.log(LogLevel.BRIEF)
    else:
        print(result)


if __name__ == "__main__":
    main()
