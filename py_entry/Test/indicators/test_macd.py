import path_tool
from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.data_conversion.input import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    _test_indicator_accuracy,
)
from py_entry.Test.utils.conftest import data_dict


# MACD引擎提取器
def macd_engine_extractor(
    indicators_df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict,
) -> Dict[str, np.ndarray]:
    result = {}
    for suffix in suffixes:
        col_name = f"{indicator_key}_{suffix}"
        result[col_name] = indicators_df[col_name].to_numpy()
    return result


# MACD pandas_ta提取器
def macd_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    fast_period = int(params["fast_period"].value)
    slow_period = int(params["slow_period"].value)
    signal_period = int(params["signal_period"].value)

    macd_df = ta.macd(
        df["close"],
        fast=fast_period,
        slow=slow_period,
        signal=signal_period,
        talib=enable_talib,
    )

    _s = ["MACD", "MACDh", "MACDs"]
    result = {}
    for suffix_ta, suffix_custom in zip(_s, suffixes):
        col_name_ta = f"{suffix_ta}_{fast_period}_{slow_period}_{signal_period}"
        col_name_custom = f"{indicator_key}_{suffix_custom}"

        result[col_name_custom] = macd_df[col_name_ta].to_numpy()

    return result


# MACD配置
macd_config = IndicatorTestConfig(
    indicator_name="macd",
    params_config={
        "ohlcv": [
            # timeframe 0
            {
                "macd_0": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "macd_1": {
                    "fast_period": Param.create(5),
                    "slow_period": Param.create(40),
                    "signal_period": Param.create(5),
                },
            },
            # timeframe 1
            {
                "macd_0": {
                    "fast_period": Param.create(8),
                    "slow_period": Param.create(21),
                    "signal_period": Param.create(7),
                },
                "macd_1": {
                    "fast_period": Param.create(10),
                    "slow_period": Param.create(30),
                    "signal_period": Param.create(10),
                },
            },
        ]
    },
    suffixes=["macd", "hist", "signal"],
    engine_result_extractor=macd_engine_extractor,
    pandas_ta_result_extractor=macd_pandas_ta_extractor,
    tolerance_customizer=None,
)


# 测试函数
def test_accuracy(data_dict):
    """测试MACD指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        macd_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=False,
    )
