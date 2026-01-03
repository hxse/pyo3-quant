from typing import Dict, Any
from py_entry.types import OptimizationResult
# To convert dict params to SingleParamSet, we might need helper builders
# But SingleParamSet expects Pydantic models.
# OptimizationResult.best_params is a dict.
# We probably need to reconstruct SingleParamSet from the initial SetupConfig structure
# but injecting the best values.
# For now, let's just expose best_params as dict, same as current impl,
# or try to keep it simple. The user request draft code showed:
# opt.best_params (which they printed).


class OptimizeResult:
    """优化结果"""

    def __init__(self, raw_result: OptimizationResult):
        self._raw = raw_result

    @property
    def best_params(self) -> Dict[str, Any]:
        """获取最优参数集 (Dict format currently)"""
        return self._raw.best_params

    @property
    def summary_table(self) -> str:
        """优化过程摘要表"""
        # This could be formatted string of history
        return str(self._raw.history)

    @property
    def raw(self) -> OptimizationResult:
        return self._raw

    @property
    def best_backtest_params(self) -> Dict[str, Any]:
        return self._raw.best_backtest_params

    @property
    def total_samples(self) -> int:
        return self._raw.total_samples

    @property
    def rounds(self) -> int:
        return self._raw.rounds

    @property
    def best_calmar(self) -> float:
        return self._raw.best_calmar
