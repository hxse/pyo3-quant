from typing import Any
from typing import Dict
from typing import List

import optuna

from py_entry.types import ParamType
from py_entry.types import SingleParamSet


class ParamInfo:
    """参数元信息，供采样与写回阶段共享。"""

    def __init__(self, type_idx: int, group: str, name: str, param_obj: Any):
        # type_idx: 0=indicator, 1=signal, 2=backtest
        self.type_idx = type_idx
        self.group = group
        self.name = name
        self.param_obj = param_obj
        self.unique_key = f"{type_idx}_{group}_{name}"


def extract_optimizable_params(params: SingleParamSet) -> List[ParamInfo]:
    """提取所有标记了 optimize=True 的参数。"""
    infos: list[ParamInfo] = []

    # 1) Indicators
    for tf, groups in params.indicators.items():
        for group_name, p_map in groups.items():
            for p_name, p_obj in p_map.items():
                if p_obj.optimize:
                    infos.append(ParamInfo(0, f"{tf}:{group_name}", p_name, p_obj))

    # 2) Signal
    for p_name, p_obj in params.signal.items():
        if p_obj.optimize:
            infos.append(ParamInfo(1, "", p_name, p_obj))

    # 3) Backtest
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


def sample_trial_values(
    trial: optuna.Trial, param_infos: List[ParamInfo]
) -> Dict[str, Any]:
    """从 trial 中采样参数值。"""
    trial_vals: dict[str, Any] = {}

    for info in param_infos:
        p = info.param_obj
        # 与 Rust 侧一致：使用 Param 内部 min/max 作为采样边界
        p_min = p.min
        p_max = p.max

        if p.dtype == ParamType.Integer:
            val = trial.suggest_int(
                info.unique_key,
                int(p_min),
                int(p_max),
                log=p.log_scale,
                step=max(1, int(p.step)) if p.step > 0 else 1,
            )
        elif p.dtype == ParamType.Boolean:
            # 统一输出为数值，便于后续回写 Param.value
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
