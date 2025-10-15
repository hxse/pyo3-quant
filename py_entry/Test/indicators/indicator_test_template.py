from dataclasses import dataclass
from typing import List, Dict, Any, Callable
import numpy as np
import pandas as pd

from py_entry.data_conversion.backtest_runner import (
    BacktestRunner,
    DefaultDataBuilder,
    DefaultParamBuilder,
    DefaultEngineSettingsBuilder,
    EngineSettings,
    ExecutionStage,
)
from py_entry.Test.utils.comparison_tool import (
    assert_indicator_same,
    assert_indicator_different,
)


@dataclass
class IndicatorTestConfig:
    """指标测试配置"""

    indicator_name: str  # 指标名称,如"bbands"

    # 参数配置(每个timeframe一套),使用标准命名: bbands_0, bbands_1, ...
    params_config: List[Dict[str, Dict[str, Any]]]

    # 回测引擎结果提取器
    # 输入: (indicators polars DataFrame, indicator_key, params_dict)
    # 输出: Dict[列名, np.ndarray]
    engine_result_extractor: Callable[[Any, str, Dict], Dict[str, np.ndarray]]

    # pandas-ta结果提取器
    # 输入: (ohlcv pandas DataFrame, indicator_key, params_dict, use_talib)
    # 输出: Dict[列名, np.ndarray]
    pandas_ta_result_extractor: Callable[
        [pd.DataFrame, str, Dict, bool], Dict[str, np.ndarray]
    ]


def _test_indicator_accuracy(
    config: IndicatorTestConfig,
    data_dict,
    enable_talib: bool = False,
    assert_mode_talib: bool = True,  # True=预期与talib相同, False=预期不同
    assert_mode_pandas_ta: bool = True,  # True=预期与pandas_ta相同, False=预期不同
):
    """
    通用指标测试模板

    逻辑:
    1. 根据config.params_config自动生成CustomParamBuilder
    2. 运行回测引擎(使用CustomEngineSettingsBuilder,设置execution_stage=INDICATOR)
    3. 对每个timeframe的每个indicator_key:
       a. 使用engine_result_extractor提取回测引擎结果
       b. 使用pandas_ta_result_extractor提取pandas_ta结果
       c. 根据assert_mode参数决定使用assert_indicator_same还是assert_indicator_different
    """

    class CustomDataBuilder(DefaultDataBuilder):
        def __init__(self, data):
            self.data = data

        def build_data_dict(self):
            return self.data

    class CustomParamBuilder(DefaultParamBuilder):
        def __init__(self, params_config):
            self.params_config = params_config

        def build_indicators_params(self, period_count: int):
            return self.params_config

    class CustomSettingsBuilder(DefaultEngineSettingsBuilder):
        def build_engine_settings(self) -> EngineSettings:
            return EngineSettings(
                execution_stage=ExecutionStage.INDICATOR,
                return_only_final=True,
                skip_risk=True,
            )

    timeframes, data = data_dict
    ohlcv_dfs = data.ohlcv

    runner = BacktestRunner()
    backtest_results = (
        runner.with_data(data_builder=CustomDataBuilder(data))
        .with_param_set(
            {"param_count": 1}, param_builder=CustomParamBuilder(config.params_config)
        )
        .with_templates()
        .with_engine_settings(engine_settings_builder=CustomSettingsBuilder())
        .run()
    )

    for timeframe_idx, timeframe_params in enumerate(config.params_config):
        indicators_df_current_timeframe = backtest_results[0].indicators[timeframe_idx]
        for indicator_key, params_dict in timeframe_params.items():
            # 提取回测引擎结果
            engine_results = config.engine_result_extractor(
                indicators_df_current_timeframe, indicator_key, params_dict
            )

            # 将Polars DataFrame转换为Pandas DataFrame以兼容pandas_ta
            pandas_df = ohlcv_dfs[timeframe_idx].to_pandas()
            # 提取pandas_ta结果
            pandas_ta_results = config.pandas_ta_result_extractor(
                pandas_df, indicator_key, params_dict, enable_talib=False
            )

            # 比较结果
            indicator_info = f"{indicator_key}: {params_dict}"
            # 提取numpy数组
            engine_array = engine_results[indicator_key]
            pandas_ta_array = pandas_ta_results[indicator_key]

            assert_func = (
                assert_indicator_same
                if assert_mode_pandas_ta
                else assert_indicator_different
            )
            assert_func(
                engine_array,
                pandas_ta_array,
                config.indicator_name,
                indicator_info,
            )

            if enable_talib:
                talib_results = config.pandas_ta_result_extractor(
                    pandas_df, indicator_key, params_dict, enable_talib=True
                )
                talib_array = talib_results[indicator_key]
                assert_func = (
                    assert_indicator_same
                    if assert_mode_talib
                    else assert_indicator_different
                )
                assert_func(
                    engine_array,
                    talib_array,
                    config.indicator_name,
                    indicator_info,
                )
