from .registry import StrategyRegistry

# 恢复新策略的导入
from .trend import TrendStrategy
from .reversal import ReversalStrategy
from .momentum import MomentumStrategy

__all__ = ["StrategyRegistry"]
