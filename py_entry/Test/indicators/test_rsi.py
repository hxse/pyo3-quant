import path_tool
from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.data_conversion.helpers import create_param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    _test_indicator_accuracy,
)
from py_entry.Test.utils.conftest import data_dict


# RSI引擎提取器(单列指标)
def rsi_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    """从回测引擎的indicators DataFrame中提取RSI单列"""
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# RSI pandas_ta提取器
def rsi_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """使用pandas_ta计算RSI,返回Dict格式"""
    period = int(params["period"].value)
    result = ta.rsi(df["close"], length=period, talib=enable_talib)
    return {indicator_key: result.to_numpy()}


# RSI配置
rsi_config = IndicatorTestConfig(
    indicator_name="rsi",
    params_config=[
        # timeframe 0
        {
            "rsi_0": {"period": create_param(14)},
            "rsi_1": {"period": create_param(21)},
        },
        # timeframe 1
        {
            "rsi_0": {"period": create_param(9)},
            "rsi_1": {"period": create_param(25)},
        },
    ],
    suffixes=[],
    engine_result_extractor=rsi_engine_extractor,
    pandas_ta_result_extractor=rsi_pandas_ta_extractor,
)


# 测试函数
def test_accuracy(data_dict):
    """测试RSI指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        rsi_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=False,
    )
