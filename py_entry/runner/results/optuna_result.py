from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class OptunaOptResult:
    """Optuna 优化结果封装"""

    best_params: Dict[str, Any]  # 最优指标参数 (timeframe:group/param:value)
    best_signal_params: Dict[str, Any]  # 最优信号参数
    best_backtest_params: Dict[str, Any]  # 最优回测参数
    best_value: float  # 最优目标值
    n_trials: int  # 总试验次数
    history: List[Dict[str, Any]] = field(default_factory=list)  # 优化历史
    study: Optional[Any] = None  # optuna.Study 实例
