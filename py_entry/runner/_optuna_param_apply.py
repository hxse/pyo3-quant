from typing import Any
from typing import Dict
from typing import List

from py_entry.types import SingleParamSet

from py_entry.runner._optuna_sampling import ParamInfo


def _clone_param_with_value(param: Any, value: float | int) -> Any:
    """复制 Param 并仅覆盖 value 字段。"""
    return param.__class__(
        value=value,
        min=param.min,
        max=param.max,
        dtype=param.dtype,
        optimize=param.optimize,
        log_scale=param.log_scale,
        step=param.step,
    )


def build_param_set(
    base_params: SingleParamSet,
    param_infos: List[ParamInfo],
    trial_values: Dict[str, Any],
) -> SingleParamSet:
    """根据采样值构建新的参数集（新对象 + 最小必要拷贝）。"""
    indicator_updates: dict[tuple[str, str, str], Any] = {}
    signal_updates: dict[str, Any] = {}
    backtest_updates: dict[str, Any] = {}

    for info in param_infos:
        val = trial_values.get(info.unique_key)
        if val is None:
            continue

        if info.type_idx == 0:
            tf, group_name = info.group.split(":")
            indicator_updates[(tf, group_name, info.name)] = val
        elif info.type_idx == 1:
            signal_updates[info.name] = val
        elif info.type_idx == 2:
            backtest_updates[info.name] = val

    # indicators: 仅在命中更新时拷贝对应路径，其他结构复用。
    indicators = base_params.indicators
    if indicator_updates:
        indicators = dict(base_params.indicators)
        copied_tf: set[str] = set()
        copied_group: set[tuple[str, str]] = set()
        for (tf, group_name, param_name), value in indicator_updates.items():
            if tf not in copied_tf:
                indicators[tf] = dict(indicators[tf])
                copied_tf.add(tf)
            group_key = (tf, group_name)
            if group_key not in copied_group:
                indicators[tf][group_name] = dict(indicators[tf][group_name])
                copied_group.add(group_key)
            old_param = indicators[tf][group_name][param_name]
            indicators[tf][group_name][param_name] = _clone_param_with_value(
                old_param, value
            )

    # signal: 仅拷贝命中的键。
    signal = base_params.signal
    if signal_updates:
        signal = dict(base_params.signal)
        for name, value in signal_updates.items():
            signal[name] = _clone_param_with_value(signal[name], value)

    # backtest: 仅存在更新时才新建对象，且只替换命中的 Param 字段。
    backtest_config = base_params.backtest
    if backtest_updates:
        bp = base_params.backtest
        maybe_param_fields = [
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
        kwargs: dict[str, Any] = {}
        for field in maybe_param_fields:
            obj = getattr(bp, field)
            if field in backtest_updates and obj is not None:
                kwargs[field] = _clone_param_with_value(obj, backtest_updates[field])
            elif obj is not None:
                kwargs[field] = obj

        backtest_config = bp.__class__(
            initial_capital=bp.initial_capital,
            fee_fixed=bp.fee_fixed,
            fee_pct=bp.fee_pct,
            tsl_atr_tight=bp.tsl_atr_tight,
            sl_exit_in_bar=bp.sl_exit_in_bar,
            tp_exit_in_bar=bp.tp_exit_in_bar,
            sl_trigger_mode=bp.sl_trigger_mode,
            tp_trigger_mode=bp.tp_trigger_mode,
            tsl_trigger_mode=bp.tsl_trigger_mode,
            sl_anchor_mode=bp.sl_anchor_mode,
            tp_anchor_mode=bp.tp_anchor_mode,
            tsl_anchor_mode=bp.tsl_anchor_mode,
            **kwargs,
        )

    # 每个 trial 创建新 SingleParamSet；performance 不参与采样，直接复用。
    return SingleParamSet(
        indicators=indicators,
        signal=signal,
        backtest=backtest_config,
        performance=base_params.performance,
    )


def get_best_params_structure(
    param_infos: List[ParamInfo], best_values: Dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """转换扁平的最优参数为原始结构。"""
    indicators: dict[str, Any] = {}
    signal: dict[str, Any] = {}
    backtest: dict[str, Any] = {}

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
