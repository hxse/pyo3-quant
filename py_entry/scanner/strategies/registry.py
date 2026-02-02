from typing import Type
from .base import StrategyProtocol


class StrategyRegistry:
    """策略注册中心"""

    _strategies: dict[str, Type[StrategyProtocol]] = {}

    @classmethod
    def register(cls, strategy_class: Type[StrategyProtocol]):
        """注册策略（装饰器用法）"""
        cls._strategies[strategy_class.name] = strategy_class
        return strategy_class

    @classmethod
    def get(cls, name: str) -> Type[StrategyProtocol] | None:
        return cls._strategies.get(name)

    @classmethod
    def get_all(cls) -> list[Type[StrategyProtocol]]:
        return list(cls._strategies.values())

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._strategies.keys())
