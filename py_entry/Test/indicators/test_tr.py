from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.data_conversion.types import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    validate_indicator_accuracy,
)


# TR引擎提取器(单列指标)
def tr_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    """
    从回测引擎的indicators DataFrame中提取TR单列
    indicator_key格式: tr_0, tr_1
    返回Dict保持与BBands一致的接口
    """
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# tr pandas_ta提取器
def tr_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """使用pandas_ta计算TR,返回Dict格式"""
    result = ta.true_range(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        talib=enable_talib,
    )

    return {indicator_key: result.to_numpy()}


# tr配置(保留原有的两个timeframe参数配置)
tr_config = IndicatorTestConfig(
    indicator_name="tr",
    params_config={
        "ohlcv_15m": {
            "tr_0": {},
        },
        "ohlcv_1h": {
            "tr_0": {},
        },
    },
    suffixes=[],
    engine_result_extractor=tr_engine_extractor,
    pandas_ta_result_extractor=tr_pandas_ta_extractor,
)


# 重构后的测试函数(保持原有签名以兼容现有测试)
def test_accuracy(data_dict):
    """测试TR指标计算结果与pandas-ta的一致性"""
    validate_indicator_accuracy(
        tr_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=False,
    )
