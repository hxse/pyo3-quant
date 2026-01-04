import optuna
import copy
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from loguru import logger
from types import SimpleNamespace

from py_entry.types import (
    SingleParamSet,
    OptunaConfig,
    ParamType,
    OptimizeMetric,
)
from py_entry.runner.results.optuna_result import OptunaOptResult

if TYPE_CHECKING:
    from py_entry.runner.backtest import Backtest


class ParamInfo:
    def __init__(self, type_idx: int, group: str, name: str, param_obj: Any):
        self.type_idx = type_idx  # 0: indicator, 1: signal, 2: backtest
        self.group = group
        self.name = name
        self.param_obj = param_obj
        self.unique_key = f"{type_idx}_{group}_{name}"


def extract_optimizable_params(params: SingleParamSet) -> List[ParamInfo]:
    """提取所有标记了 optimize=True 的参数"""
    infos = []

    # 1. Indicators
    for tf, groups in params.indicators.items():
        for group_name, p_map in groups.items():
            for p_name, p_obj in p_map.items():
                if p_obj.optimize:
                    infos.append(ParamInfo(0, f"{tf}:{group_name}", p_name, p_obj))

    # 2. Signal
    for p_name, p_obj in params.signal.items():
        if p_obj.optimize:
            infos.append(ParamInfo(1, "", p_name, p_obj))

    # 3. Backtest
    backtest_fields = [
        "sl_pct",
        "tp_pct",
        "tsl_pct",
        "sl_atr",
        "tp_atr",
        "tsl_atr",
        "atr_period",
        "tsl_psar_af0",
        "tsl_psar_af_step",
        "tsl_psar_max_af",
    ]
    for field in backtest_fields:
        p_obj = getattr(params.backtest, field)
        if p_obj and p_obj.optimize:
            infos.append(ParamInfo(2, "", field, p_obj))

    return infos


def build_param_set(
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    trial_values: Dict[str, Any],
) -> SingleParamSet:
    """根据采样值构建新的参数集"""
    new_params = copy.deepcopy(base_params)

    for info in param_infos:
        val = trial_values.get(info.unique_key)
        if val is None:
            continue

        if info.type_idx == 0:
            # Indicator
            tf, group_name = info.group.split(":")
            new_params.indicators[tf][group_name][info.name].value = val
        elif info.type_idx == 1:
            # Signal
            new_params.signal[info.name].value = val
        elif info.type_idx == 2:
            # Backtest
            p_obj = getattr(new_params.backtest, info.name)
            if p_obj:
                p_obj.value = val

    return new_params


def get_best_params_structure(
    param_infos: List[ParamInfo], best_values: Dict[str, Any]
):
    """转换扁平的最优参数为原始结构"""
    indicators = {}
    signal = {}
    backtest = {}

    for info in param_infos:
        val = best_values.get(info.unique_key)
        if val is None:
            continue

        if info.type_idx == 0:
            tf, group = info.group.split(":")
            if tf not in indicators:
                indicators[tf] = {}
            if group not in indicators[tf]:
                indicators[tf][group] = {}
            indicators[tf][group][info.name] = val
        elif info.type_idx == 1:
            signal[info.name] = val
        elif info.type_idx == 2:
            backtest[info.name] = val

    return indicators, signal, backtest


def run_optuna_optimization(
    backtest: "Backtest",
    config: OptunaConfig,
    params_override: Optional[SingleParamSet] = None,
) -> OptunaOptResult:
    """执行 Optuna 优化核心逻辑"""

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

    metric_key = (
        config.metric.value
        if isinstance(config.metric, OptimizeMetric)
        else config.metric
    )

    # 根据 n_jobs 选择执行模式
    if config.n_jobs == 1:
        # 原有的 ask/tell 批量模式 (利用 Rust batch 并行)
        _run_batch_mode(study, backtest, base_params, param_infos, config, metric_key)
    else:
        # n_jobs 并行模式 (利用 joblib 多进程)
        _run_parallel_mode(
            study, backtest, base_params, param_infos, config, metric_key
        )

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


def _run_batch_mode(
    study: optuna.Study,
    backtest: "Backtest",
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    config: OptunaConfig,
    metric_key: str,
):
    """批量 ask/tell 模式 (利用 Rust batch 并行)"""
    n_trials_done = 0

    while n_trials_done < config.n_trials:
        current_batch_size = min(config.batch_size, config.n_trials - n_trials_done)

        # 1. 批量采样 (Ask)
        trials = []
        batch_param_sets = []

        for _ in range(current_batch_size):
            trial = study.ask()
            trials.append(trial)

            # 定义搜索空间并采样
            trial_vals = _sample_trial_values(trial, param_infos)
            batch_param_sets.append(
                build_param_set(base_params, param_infos, trial_vals)
            )

        # 2. 批量回测 (利用 backtest.batch 的并行能力)
        batch_result = backtest.batch(batch_param_sets)

        # 3. 反馈结果 (Tell)
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


def _run_parallel_mode(
    study: optuna.Study,
    backtest: "Backtest",
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    config: OptunaConfig,
    metric_key: str,
):
    """n_jobs 并行模式 (使用 study.optimize)"""

    def objective(trial: optuna.Trial) -> float:
        # 采样参数
        trial_vals = _sample_trial_values(trial, param_infos)
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


def _sample_trial_values(
    trial: optuna.Trial, param_infos: List[ParamInfo]
) -> Dict[str, Any]:
    """从 trial 中采样参数值"""
    trial_vals = {}
    for info in param_infos:
        p = info.param_obj
        # 处理 min/max 的 fallback 逻辑，与 Rust 侧保持一致
        p_min = p.min
        p_max = p.max

        if p.dtype == ParamType.INTEGER:
            val = trial.suggest_int(
                info.unique_key,
                int(p_min),
                int(p_max),
                log=p.log_scale,
                step=int(p.step) if p.step > 0 else 1,
            )
        elif p.dtype == ParamType.BOOLEAN:
            val = (
                1.0
                if trial.suggest_categorical(info.unique_key, [True, False])
                else 0.0
            )
        else:
            val = trial.suggest_float(
                info.unique_key,
                p_min,
                p_max,
                log=p.log_scale,
                step=p.step if p.step > 0 else None,
            )
        trial_vals[info.unique_key] = val

    return trial_vals
