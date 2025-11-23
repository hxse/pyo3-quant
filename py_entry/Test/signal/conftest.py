import pytest
from py_entry.data_conversion.helpers.data_generator import (
    generate_data_dict,
    DataGenerationParams,
)
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.input import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    Param,
    CompareOp,
    LogicOp,
    SignalGroup,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)


# 自定义指标参数
custom_indicators_params: IndicatorsParams = {
    "ohlcv": [
        {
            "bbands_0": {"period": Param.create(20), "std": Param.create(2)},
        },
        {
            "rsi_0": {"period": Param.create(14)},
        },
        {
            "sma_0": {"period": Param.create(8)},
            "sma_1": {"period": Param.create(20)},
        },
    ]
}

# 自定义信号参数
custom_signal_params: SignalParams = {
    "rsi_upper": Param.create(80),
    "rsi_lower": Param.create(20),
}

# 自定义信号模板
enter_long_group_custom = SignalGroup(
    logic=LogicOp.AND,
    conditions=[
        signal_data_vs_data(
            compare=CompareOp.GT,
            a_name="sma_0",
            a_source="ohlcv_2",
            a_offset=0,
            b_name="sma_1",
            b_source="ohlcv_2",
            b_offset=0,
        ),
        signal_data_vs_param(
            compare=CompareOp.LT,
            a_name="rsi_0",
            a_source="ohlcv_1",
            a_offset=0,
            b_param="rsi_lower",
        ),
        signal_data_vs_data(
            compare=CompareOp.CGT,
            a_name="close",
            a_source="ohlcv_0",
            a_offset=0,
            b_name="bbands_0_upper",
            b_source="ohlcv_0",
            b_offset=0,
        ),
    ],
)

exit_long_group_custom = SignalGroup(
    logic=LogicOp.OR,
    conditions=[
        signal_data_vs_data(
            compare=CompareOp.LT,
            a_name="close",
            a_source="ohlcv_0",
            a_offset=0,
            b_name="bbands_0_upper",
            b_source="ohlcv_0",
            b_offset=0,
        ),
    ],
)

enter_short_group_custom = SignalGroup(
    logic=LogicOp.AND,
    conditions=[
        signal_data_vs_data(
            compare=CompareOp.LT,
            a_name="sma_0",
            a_source="ohlcv_2",
            a_offset=0,
            b_name="sma_1",
            b_source="ohlcv_2",
            b_offset=0,
        ),
        signal_data_vs_param(
            compare=CompareOp.GT,
            a_name="rsi_0",
            a_source="ohlcv_1",
            a_offset=0,
            b_param="rsi_upper",
        ),
        signal_data_vs_data(
            compare=CompareOp.CLT,
            a_name="close",
            a_source="ohlcv_0",
            a_offset=0,
            b_name="bbands_0_lower",
            b_source="ohlcv_0",
            b_offset=0,
        ),
    ],
)

exit_short_group_custom = SignalGroup(
    logic=LogicOp.OR,
    conditions=[
        signal_data_vs_data(
            compare=CompareOp.GT,
            a_name="close",
            a_source="ohlcv_0",
            a_offset=0,
            b_name="bbands_0_lower",
            b_source="ohlcv_0",
            b_offset=0,
        ),
    ],
)

custom_signal_template: SignalTemplate = SignalTemplate(
    name="simplified_multi_timeframe_strategy",
    enter_long=[enter_long_group_custom],
    exit_long=[exit_long_group_custom],
    enter_short=[enter_short_group_custom],
    exit_short=[exit_short_group_custom],
)

# 自定义引擎设置
custom_engine_settings: SettingContainer = SettingContainer(
    execution_stage=ExecutionStage.SIGNALS,  # 确保返回signals数据
    return_only_final=False,
)


@pytest.fixture(scope="module")
def signal_backtest_results():
    """配置并运行回测，返回结果和数据容器"""
    runner = BacktestRunner()

    # 直接创建数据配置
    data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=5000,
    )

    # 使用 setup 方法一次性配置所有参数
    runner.setup(
        data_source=data_config,
        indicators_params=custom_indicators_params,
        signal_params=custom_signal_params,
        signal_template=custom_signal_template,
        engine_settings=custom_engine_settings,
    )

    # 运行回测并获取结果
    results = runner.run()

    # 返回结果、数据字典和信号参数
    return results[0], runner._data_dict, custom_signal_params
