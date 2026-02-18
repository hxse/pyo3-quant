"""
策略注册表

通过动态导入 strategies/ 目录下的所有策略模块，自动注册策略。
每个策略模块需要实现 get_config() -> StrategyConfig 函数。
"""

from typing import List, Dict, Callable
from pathlib import Path
import importlib

from .base import StrategyConfig

# 策略注册表：策略名称 -> 获取配置的函数
STRATEGY_REGISTRY: Dict[str, Callable[[], StrategyConfig]] = {}


def register_strategy(name: str):
    """装饰器：注册策略到注册表"""

    def decorator(fn: Callable[[], StrategyConfig]):
        STRATEGY_REGISTRY[name] = fn
        return fn

    return decorator


def get_strategy(name: str) -> StrategyConfig:
    """获取指定策略的配置"""
    if name not in STRATEGY_REGISTRY:
        raise KeyError(
            f"策略 '{name}' 未注册。可用策略: {list(STRATEGY_REGISTRY.keys())}"
        )
    return STRATEGY_REGISTRY[name]()


def get_all_strategies() -> List[StrategyConfig]:
    """获取所有已注册策略的配置列表"""
    return [fn() for fn in STRATEGY_REGISTRY.values()]


def get_strategy_names() -> List[str]:
    """获取所有已注册策略的名称"""
    return list(STRATEGY_REGISTRY.keys())


def _auto_discover_strategies():
    """自动发现并导入 strategies/ 目录下的所有策略模块"""
    strategies_dir = Path(__file__).parent

    # 1. 发现单文件策略（如 atr_stoploss.py）
    for py_file in strategies_dir.glob("*.py"):
        module_name = py_file.stem
        # 跳过 __init__.py、base.py 和备份文件
        if (
            module_name.startswith("_")
            or module_name == "base"
            or module_name.endswith(".bak")
        ):
            continue
        # 动态导入模块，触发 @register_strategy 装饰器
        importlib.import_module(f".{module_name}", package=__package__)

    # 2. 发现子目录策略（如 sma_crossover/）
    for subdir in strategies_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("_"):
            # 检查子目录是否包含 __init__.py
            if (subdir / "__init__.py").exists():
                # 导入子目录（会自动执行其 __init__.py）
                importlib.import_module(f".{subdir.name}", package=__package__)


# 模块加载时自动发现策略
_auto_discover_strategies()
