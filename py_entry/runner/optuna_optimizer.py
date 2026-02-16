from typing import TYPE_CHECKING
from typing import Optional

import optuna

from py_entry.runner._optuna_execution import run_batch_mode
from py_entry.runner._optuna_execution import run_parallel_mode
from py_entry.runner._optuna_param_apply import get_best_params_structure
from py_entry.runner._optuna_sampling import extract_optimizable_params
from py_entry.runner.results.optuna_result import OptunaOptResult
from py_entry.types import OptunaConfig
from py_entry.types import OptimizeMetric
from py_entry.types import SingleParamSet

if TYPE_CHECKING:
    from py_entry.runner.backtest import Backtest


def run_optuna_optimization(
    backtest: "Backtest",
    config: OptunaConfig,
    params_override: Optional[SingleParamSet] = None,
) -> OptunaOptResult:
    """执行 Optuna 优化核心逻辑。"""

    base_params = params_override or backtest.params
    param_infos = extract_optimizable_params(base_params)

    if not param_infos:
        raise ValueError("No parameters marked for optimization (optimize=True)")

    # 创建 Study
    sampler = None
    if config.sampler == "TPE":
        sampler = optuna.samplers.TPESampler(seed=config.seed)
    elif config.sampler == "CMA-ES":
        sampler = optuna.samplers.CmaEsSampler(seed=config.seed)
    elif config.sampler == "Random":
        sampler = optuna.samplers.RandomSampler(seed=config.seed)
    elif config.sampler == "NSGAII":
        sampler = optuna.samplers.NSGAIISampler(seed=config.seed)

    study = optuna.create_study(
        study_name=config.study_name,
        storage=config.storage,
        direction=config.direction,
        sampler=sampler,
        load_if_exists=True,
    )

    # 将 OptimizeMetric 映射为性能字典键名
    metric_key = config.metric
    if isinstance(config.metric, OptimizeMetric):
        metric_key = config.metric.as_str()

    # 根据 n_jobs 选择执行模式
    if config.n_jobs == 1:
        run_batch_mode(study, backtest, base_params, param_infos, config, metric_key)
    else:
        run_parallel_mode(study, backtest, base_params, param_infos, config, metric_key)

    # 构建最终结果
    best_indicators, best_signal, best_backtest = get_best_params_structure(
        param_infos, study.best_params
    )

    history = []
    for t in study.trials:
        if t.state == optuna.trial.TrialState.COMPLETE:
            history.append({"number": t.number, "value": t.value, "params": t.params})

    return OptunaOptResult(
        best_params=best_indicators,
        best_signal_params=best_signal,
        best_backtest_params=best_backtest,
        best_value=study.best_value,
        n_trials=len(study.trials),
        history=history,
        study=study,
    )
