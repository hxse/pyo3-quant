from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.data_conversion.input import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    _test_indicator_accuracy,
)


# SMA引擎提取器(单列指标)
def sma_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    """
    从回测引擎的indicators DataFrame中提取SMA单列
    indicator_key格式: sma_0, sma_1
    返回Dict保持与BBands一致的接口
    """
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# SMA pandas_ta提取器
def sma_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """使用pandas_ta计算SMA,返回Dict格式"""
    period = int(params["period"].value)
    result = ta.sma(df["close"], length=period, talib=enable_talib)
    return {indicator_key: result.to_numpy()}


# SMA配置(保留原有的两个timeframe参数配置)
sma_config = IndicatorTestConfig(
    indicator_name="sma",
    params_config={
        "ohlcv": [
            # timeframe 0
            {
                "sma_0": {"period": Param.create(14)},
                "sma_1": {"period": Param.create(100)},
            },
            # timeframe 1
            {
                "sma_0": {"period": Param.create(20)},
                "sma_1": {"period": Param.create(200)},
            },
        ]
    },
    suffixes=[],
    engine_result_extractor=sma_engine_extractor,
    pandas_ta_result_extractor=sma_pandas_ta_extractor,
)


# 重构后的测试函数(保持原有签名以兼容现有测试)
def test_accuracy(data_dict):
    """测试SMA指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        sma_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=True,
    )
