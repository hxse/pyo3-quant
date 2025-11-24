from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.data_conversion.types import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    validate_indicator_accuracy,
)


# ATR引擎提取器(单列指标)
def atr_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    """从回测引擎的indicators DataFrame中提取ATR单列"""
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# ATR pandas_ta提取器
def atr_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """使用pandas_ta计算ATR,返回Dict格式"""
    period = int(params["period"].value)
    result = ta.atr(
        df["high"], df["low"], df["close"], length=period, talib=enable_talib
    )
    return {indicator_key: result.to_numpy()}


# ATR配置
atr_config = IndicatorTestConfig(
    indicator_name="atr",
    params_config={
        "ohlcv_15m": {
            "atr_0": {"period": Param.create(14)},
            "atr_1": {"period": Param.create(20)},
        },
        "ohlcv_1h": {
            "atr_0": {"period": Param.create(20)},
            "atr_1": {"period": Param.create(30)},
        },
    },
    suffixes=[],
    engine_result_extractor=atr_engine_extractor,
    pandas_ta_result_extractor=atr_pandas_ta_extractor,
)


# 测试函数
def test_accuracy(data_dict):
    """测试ATR指标计算结果与pandas-ta的一致性"""
    validate_indicator_accuracy(
        atr_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=False,
    )
