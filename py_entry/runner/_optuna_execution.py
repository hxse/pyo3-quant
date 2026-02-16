from typing import TYPE_CHECKING
from typing import Any
from typing import List

import optuna
from loguru import logger

from py_entry.types import OptunaConfig
from py_entry.types import SingleParamSet

from py_entry.runner._optuna_param_apply import build_param_set
from py_entry.runner._optuna_sampling import ParamInfo
from py_entry.runner._optuna_sampling import sample_trial_values

if TYPE_CHECKING:
    from py_entry.runner.backtest import Backtest


def run_batch_mode(
    study: optuna.Study,
    backtest: "Backtest",
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    config: OptunaConfig,
    metric_key: str,
) -> None:
    """批量 ask/tell 模式（利用 Rust batch 并行）。"""
    n_trials_done = 0

    while n_trials_done < config.n_trials:
        current_batch_size = min(config.batch_size, config.n_trials - n_trials_done)

        # 1) 批量采样 (Ask)
        trials: list[optuna.Trial] = []
        batch_param_sets: list[SingleParamSet] = []
        for _ in range(current_batch_size):
            trial = study.ask()
            trials.append(trial)
            trial_vals = sample_trial_values(trial, param_infos)
            batch_param_sets.append(
                build_param_set(base_params, param_infos, trial_vals)
            )

        # 2) 批量回测（利用 backtest.batch 并行能力）
        batch_result = backtest.batch(batch_param_sets)

        # 3) 反馈结果 (Tell)
        for trial, summary in zip(trials, batch_result.summaries):
            val = 0.0
            if summary.performance:
                val = summary.performance.get(metric_key, 0.0)
            study.tell(trial, val)

        n_trials_done += current_batch_size
        if config.show_progress_bar:
            logger.info(
                f"Optuna Optimization: {n_trials_done}/{config.n_trials} trials completed. Best: {study.best_value:.4f}"
            )


def run_parallel_mode(
    study: optuna.Study,
    backtest: "Backtest",
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    config: OptunaConfig,
    metric_key: str,
) -> None:
    """n_jobs 并行模式（使用 study.optimize）。"""

    def objective(trial: optuna.Trial) -> float:
        # 采样参数并构建 trial 参数集
        trial_vals = sample_trial_values(trial, param_infos)
        new_params = build_param_set(base_params, param_infos, trial_vals)

        # 单次回测
        result = backtest.run(params_override=new_params)
        if result.summary.performance:
            return result.summary.performance.get(metric_key, 0.0)
        return 0.0

    study.optimize(
        objective,
        n_trials=config.n_trials,
        n_jobs=config.n_jobs,
        show_progress_bar=config.show_progress_bar,
    )
