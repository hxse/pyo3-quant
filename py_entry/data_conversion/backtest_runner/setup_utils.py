"""
回测设置工具函数，用于替换 builder 类
"""

from py_entry.data_conversion.types import (
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
)

from py_entry.data_conversion.data_generator import (
    generate_data_dict,
    DataGenerationParams,
    OtherParams,
    DataSourceConfig,
)


def build_data(
    data_source: DataSourceConfig | None = None,
    other_params: OtherParams | None = None,
) -> DataContainer:
    """构建数据字典

    Args:
        data_source: 数据源配置，可以是三种类型之一：
            - DataGenerationParams: 模拟数据生成参数
            - OhlcvDataFetchConfig: OHLCV数据获取配置
            - list[pl.DataFrame]: 预定义的OHLCV DataFrame列表
            - None: 使用默认模拟数据配置
        other_params: 其他参数配置对象

    Returns:
        DataContainer 数据容器
    """
    # 如果 data_source 为 None，使用默认的模拟数据配置
    if data_source is None:
        data_source = DataGenerationParams(
            timeframes=["15m", "1h"],
            start_time=1735689600000,
            num_bars=3000,
            fixed_seed=42,
            BaseDataKey="ohlcv_15m",
        )

    return generate_data_dict(data_source=data_source, other_params=other_params)


def build_indicators_params(
    indicators_params: IndicatorsParams | None = None,
) -> IndicatorsParams:
    """构建指标参数

    Args:
        indicators_params: 可选的指标参数，如果提供则直接返回，为None时返回默认值

    Returns:
        IndicatorsParams 指标参数
    """
    # 如果参数不为None，直接返回提供的参数
    if indicators_params is not None:
        return indicators_params

    # 否则返回默认值
    return {
        "ohlcv_15m": {
            "sma_0": {"period": Param.create(14, 5, 50, 1)},
            "sma_1": {
                "period": Param.create(200, 100, 300, 10),
            },
        },
        "ohlcv_1h": {
            "sma_0": {"period": Param.create(14, 5, 50, 1)},
        },
    }


def build_signal_params(
    signal_params: SignalParams | None = None,
) -> SignalParams:
    """构建信号参数

    Args:
        signal_params: 可选的信号参数，如果提供则直接返回，为None时返回默认值

    Returns:
        SignalParams 信号参数
    """
    # 如果参数不为None，直接返回提供的参数
    if signal_params is not None:
        return signal_params

    # 否则返回默认值
    return {"rsi_midline": Param.create(20, 10, 90, 5)}


def build_backtest_params(
    backtest_params: BacktestParams | None = None,
) -> BacktestParams:
    """构建回测参数

    Args:
        backtest_params: 可选的回测参数，如果提供则直接返回，为None时返回默认值

    Returns:
        BacktestParams 回测参数
    """
    # 如果参数不为None，直接返回提供的参数
    if backtest_params is not None:
        return backtest_params

    # 否则返回默认值
    return BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        exit_in_bar=False,
        use_extrema_for_exit=False,
        sl_pct=Param.create(2, 0.5, 5, 0.1),
        tp_pct=Param.create(2, 0.5, 5, 0.1),
        tsl_pct=Param.create(1, 0.5, 3, 0.1),
        sl_atr=Param.create(2, 1, 5, 0.5),
        tp_atr=Param.create(3, 1, 5, 0.5),
        tsl_atr=Param.create(2, 1, 4, 0.5),
        atr_period=Param.create(14, 7, 21, 1),
    )


def build_performance_params(
    performance_params: PerformanceParams | None = None,
) -> PerformanceParams:
    """构建性能参数

    Args:
        performance_params: 可选的性能参数，如果提供则直接返回，为None时返回默认值

    Returns:
        PerformanceParams 性能参数
    """
    # 如果参数不为None，直接返回提供的参数
    if performance_params is not None:
        return performance_params

    # 否则返回默认值
    return PerformanceParams()


def build_signal_template(
    signal_template: SignalTemplate | None = None,
) -> SignalTemplate:
    """构建信号模板

    Args:
        signal_template: 可选的信号模板，如果提供则直接返回，为None时返回默认值

    Returns:
        SignalTemplate 信号模板
    """
    # 如果参数不为None，直接返回提供的参数
    if signal_template is not None:
        return signal_template

    # 否则返回默认值
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_0, ohlcv_15m, 0 > sma_1, ohlcv_15m, 0"],
    )

    return SignalTemplate(entry_long=entry_long_group)


def build_engine_settings(
    engine_settings: SettingContainer | None = None,
) -> SettingContainer:
    """构建引擎设置

    Args:
        engine_settings: 可选的引擎设置，如果提供则直接返回，为None时返回默认值

    Returns:
        SettingContainer 设置容器
    """
    # 如果参数不为None，直接返回提供的参数
    if engine_settings is not None:
        return engine_settings

    # 否则返回默认值
    return SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )
