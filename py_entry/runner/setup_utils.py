"""
回测设置工具函数，用于替换 builder 类
"""

from py_entry.types import (
    DataContainer,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    Param,
    LogicOp,
    SignalTemplate,
    SignalGroup,
    SettingContainer,
    ExecutionStage,
    PerformanceMetric,
)

from py_entry.data_generator import (
    generate_data_dict,
    DataGenerationParams,
    OtherParams,
    DataSourceConfig,
)
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def _type_error(expected: str, actual: object, path: str) -> TypeError:
    """统一构造类型错误，提升报错可读性。"""
    return TypeError(f"{path} expected {expected}, got {type(actual)}")


def build_data(
    data_source: DataSourceConfig | None = None,
    other_params: OtherParams | None = None,
) -> DataContainer:
    """构建数据字典"""
    if data_source is None:
        data_source = DataGenerationParams(
            timeframes=["15m", "1h"],
            start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
            num_bars=3000,
            fixed_seed=42,
            base_data_key="ohlcv_15m",
        )

    return generate_data_dict(data_source=data_source, other_params=other_params)


def ensure_param(v: Param) -> Param:
    """强约束参数类型，只接受 Rust 导出的 Param。"""
    if not isinstance(v, Param):
        raise _type_error("Param", v, "param")
    return v


def _ensure_signal_params(signal_params: SignalParams) -> SignalParams:
    """校验并复制 signal 参数，确保每个 value 都是 Param。"""
    converted: SignalParams = {}
    for param_name, param_value in signal_params.items():
        # 精确报错路径，便于快速定位配置问题。
        if not isinstance(param_name, str):
            raise _type_error("str", param_name, "signal_params.<key>")
        if not isinstance(param_value, Param):
            raise _type_error("Param", param_value, f"signal_params.{param_name}")
        converted[param_name] = param_value
    return converted


def build_indicators_params(
    indicators_params: IndicatorsParams | None = None,
) -> IndicatorsParams:
    """构建指标参数"""
    if indicators_params is None:
        return {
            "ohlcv_15m": {
                "sma_0": {"period": Param(14, min=5, max=50, step=1)},
                "sma_1": {
                    "period": Param(200, min=100, max=300, step=10),
                },
            },
            "ohlcv_1h": {
                "sma_0": {"period": Param(14, min=5, max=50, step=1)},
            },
        }

    # 将嵌套参数中的值统一校验为 Param，保证传给 Rust 的类型一致。
    converted: IndicatorsParams = {}
    for source_name, indicator_group in indicators_params.items():
        if not isinstance(source_name, str):
            raise _type_error("str", source_name, "indicators_params.<source_name>")
        if not isinstance(indicator_group, dict):
            raise _type_error(
                "dict[str, dict[str, Param]]",
                indicator_group,
                f"indicators_params.{source_name}",
            )
        converted_group = {}
        for indicator_name, param_map in indicator_group.items():
            if not isinstance(indicator_name, str):
                raise _type_error(
                    "str", indicator_name, "indicators_params.<indicator_name>"
                )
            if not isinstance(param_map, dict):
                raise _type_error(
                    "dict[str, Param]",
                    param_map,
                    f"indicators_params.{source_name}.{indicator_name}",
                )
            converted_params = {}
            for param_name, param_value in param_map.items():
                if not isinstance(param_name, str):
                    raise _type_error(
                        "str", param_name, "indicators_params.<param_name>"
                    )
                if not isinstance(param_value, Param):
                    raise _type_error(
                        "Param",
                        param_value,
                        f"indicators_params.{source_name}.{indicator_name}.{param_name}",
                    )
                converted_params[param_name] = param_value
            converted_group[indicator_name] = converted_params
        converted[source_name] = converted_group
    return converted


def build_signal_params(
    signal_params: SignalParams | None = None,
) -> SignalParams:
    """构建信号参数"""
    if signal_params is None:
        return {"rsi_midline": Param(20, min=10, max=90, step=5)}

    if not isinstance(signal_params, dict):
        raise _type_error("dict[str, Param]", signal_params, "signal_params")
    return _ensure_signal_params(signal_params)


def build_backtest_params(
    backtest_params: BacktestParams | None = None,
) -> BacktestParams:
    """构建回测参数"""
    if backtest_params is None:
        return BacktestParams(
            initial_capital=10000.0,
            fee_fixed=1,
            fee_pct=0.001,
            sl_exit_in_bar=False,
            tp_exit_in_bar=False,
            sl_trigger_mode=False,
            tp_trigger_mode=False,
            tsl_trigger_mode=False,
            sl_anchor_mode=False,
            tp_anchor_mode=False,
            tsl_anchor_mode=False,
            sl_pct=Param(2, min=0.5, max=5, step=0.1),
            tp_pct=Param(2, min=0.5, max=5, step=0.1),
            tsl_pct=Param(1, min=0.5, max=3, step=0.1),
            sl_atr=Param(2, min=1, max=5, step=0.5),
            tp_atr=Param(3, min=1, max=5, step=0.5),
            tsl_atr=Param(2, min=1, max=4, step=0.5),
            atr_period=Param(14, min=7, max=21, step=1),
        )

    if not isinstance(backtest_params, BacktestParams):
        raise _type_error("BacktestParams", backtest_params, "backtest_params")
    return backtest_params


def build_performance_params(
    performance_params: PerformanceParams | None = None,
) -> PerformanceParams:
    """构建性能参数"""
    if performance_params is None:
        return PerformanceParams(
            metrics=[
                PerformanceMetric.TotalReturn,
                PerformanceMetric.CalmarRatio,
                PerformanceMetric.CalmarRatioRaw,
                PerformanceMetric.TotalTrades,
                PerformanceMetric.MaxDrawdown,
            ]
        )

    if not isinstance(performance_params, PerformanceParams):
        raise _type_error("PerformanceParams", performance_params, "performance_params")
    return performance_params


def build_signal_template(
    signal_template: SignalTemplate | None = None,
) -> SignalTemplate:
    """构建信号模板"""
    if signal_template is not None:
        if not isinstance(signal_template, SignalTemplate):
            raise _type_error("SignalTemplate", signal_template, "signal_template")
        return signal_template

    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_0, ohlcv_15m, 0 > sma_1, ohlcv_15m, 0"],
    )

    return SignalTemplate(entry_long=entry_long_group)


def build_engine_settings(
    engine_settings: SettingContainer | None = None,
) -> SettingContainer:
    """构建引擎设置"""
    if engine_settings is not None:
        if not isinstance(engine_settings, SettingContainer):
            raise _type_error("SettingContainer", engine_settings, "engine_settings")
        return engine_settings

    return SettingContainer(
        execution_stage=ExecutionStage.Performance,
        return_only_final=False,
    )
