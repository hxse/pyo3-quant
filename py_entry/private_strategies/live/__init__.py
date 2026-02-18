"""
live 策略注册表。

该注册表仅用于交易机器人消费，不与示例/测试公共策略注册表混用。
"""

from pathlib import Path
from typing import Callable, Dict, List, cast
import importlib

from .base import LiveStrategyConfig


LIVE_STRATEGY_REGISTRY: Dict[str, Callable[[], LiveStrategyConfig]] = {}
_LIVE_STRATEGY_ATTR = "__live_strategy_name__"


def register_live_strategy(name: str):
    """装饰器：标记 live 策略函数。"""

    def decorator(fn: Callable[[], LiveStrategyConfig]):
        # 仅打标记，不在装饰阶段直接写注册表，避免 import research 时污染 live。
        setattr(fn, _LIVE_STRATEGY_ATTR, name)
        return fn

    return decorator


def get_live_strategy(name: str) -> LiveStrategyConfig:
    """按名称获取 live 策略。"""
    if name not in LIVE_STRATEGY_REGISTRY:
        raise KeyError(
            f"live 策略 '{name}' 未注册。可用策略: {list(LIVE_STRATEGY_REGISTRY.keys())}"
        )
    return LIVE_STRATEGY_REGISTRY[name]()


def get_all_live_strategies() -> List[LiveStrategyConfig]:
    """获取全部 live 策略配置。"""
    return [fn() for fn in LIVE_STRATEGY_REGISTRY.values()]


def get_live_strategy_names() -> List[str]:
    """获取全部 live 策略名称。"""
    return list(LIVE_STRATEGY_REGISTRY.keys())


def _auto_discover_live_strategies():
    """自动导入 live/ 下策略文件，并收集带装饰器标记的函数。"""
    live_dir = Path(__file__).parent
    for py_file in sorted(live_dir.glob("*.py"), key=lambda p: p.name):
        module_name = py_file.stem
        if module_name in {"__init__", "base"} or module_name.startswith("_"):
            continue
        module = importlib.import_module(f".{module_name}", package=__package__)
        for obj in module.__dict__.values():
            strategy_name = getattr(obj, _LIVE_STRATEGY_ATTR, None)
            if strategy_name is None:
                continue
            if not callable(obj):
                raise TypeError(f"live 策略 '{strategy_name}' 注册对象不可调用")
            if strategy_name in LIVE_STRATEGY_REGISTRY:
                raise ValueError(f"live 策略名重复注册: '{strategy_name}'")
            LIVE_STRATEGY_REGISTRY[strategy_name] = cast(
                Callable[[], LiveStrategyConfig], obj
            )


_auto_discover_live_strategies()
