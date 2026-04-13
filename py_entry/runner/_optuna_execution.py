from typing import TYPE_CHECKING
from typing import List

import optuna
import pyo3_quant
from loguru import logger

from py_entry.types import OptunaConfig
from py_entry.types import ResultPack
from py_entry.types import SettingContainer
from py_entry.types import SingleParamSet

from py_entry.runner._optuna_param_apply import build_param_set
from py_entry.runner._optuna_sampling import ParamInfo
from py_entry.runner._optuna_sampling import sample_trial_values

if TYPE_CHECKING:
    from py_entry.runner.backtest import Backtest


def _extract_trial_metric(result: ResultPack, metric_key: str) -> float:
    """提取 Optuna trial 指标，缺失时直接失败。"""
    performance = result.performance
    if performance is None:
        raise ValueError("Optuna trial 结果缺少 performance，不能计算目标指标。")
    if metric_key not in performance:
        raise KeyError(f"Optuna trial performance 缺少指标: {metric_key}")
    return performance[metric_key]


def run_batch_mode(
    study: optuna.Study,
    backtest: "Backtest",
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    config: OptunaConfig,
    metric_key: str,
    engine_settings: SettingContainer,
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

        # 2) 批量回测：Optuna 固定使用 performance-only 正式模式。
        results = pyo3_quant.backtest_engine.run_batch_backtest(
            backtest.data_pack,
            batch_param_sets,
            backtest.template_config,
            engine_settings,
        )

        # 3) 反馈结果 (Tell)
        for trial, result in zip(trials, results):
            study.tell(trial, _extract_trial_metric(result, metric_key))

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
    engine_settings: SettingContainer,
) -> None:
    """n_jobs 并行模式（使用 study.optimize）。"""

    def objective(trial: optuna.Trial) -> float:
        # 采样参数并构建 trial 参数集
        trial_vals = sample_trial_values(trial, param_infos)
        new_params = build_param_set(base_params, param_infos, trial_vals)

        # 单次回测：Optuna 固定使用 performance-only 正式模式。
        result = pyo3_quant.backtest_engine.run_single_backtest(
            backtest.data_pack,
            new_params,
            backtest.template_config,
            engine_settings,
        )
        return _extract_trial_metric(result, metric_key)

    study.optimize(
        objective,
        n_trials=config.n_trials,
        n_jobs=config.n_jobs,
        show_progress_bar=config.show_progress_bar,
    )
