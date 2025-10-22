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


# RMA引擎提取器(单列指标)
def rma_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# RMA pandas_ta提取器
def rma_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    period = int(params["period"].value)
    result = ta.rma(df["close"], length=period)
    return {indicator_key: result.to_numpy()}


# RMA配置
rma_config = IndicatorTestConfig(
    indicator_name="rma",
    params_config={
        "ohlcv": [
            # timeframe 0
            {
                "rma_0": {"period": create_param(14)},
                "rma_1": {"period": create_param(100)},
            },
            # timeframe 1
            {
                "rma_0": {"period": create_param(20)},
                "rma_1": {"period": create_param(200)},
            },
        ]
    },
    suffixes=[],
    engine_result_extractor=rma_engine_extractor,
    pandas_ta_result_extractor=rma_pandas_ta_extractor,
)


# 测试函数
def test_accuracy(data_dict):
    """测试RMA指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        rma_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=True,
    )
