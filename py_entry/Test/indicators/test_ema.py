from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta

from py_entry.types import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    validate_indicator_accuracy,
)


# EMA引擎提取器(单列指标)
def ema_engine_extractor(
    indicators_df, indicator_key: str, suffixes: list[str], params: Dict
) -> Dict[str, np.ndarray]:
    """
    从回测引擎的indicators DataFrame中提取EMA单列
    indicator_key格式: ema_0, ema_1
    返回Dict保持与BBands一致的接口
    """
    return {indicator_key: indicators_df[indicator_key].to_numpy()}


# EMA pandas_ta提取器
def ema_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """使用pandas_ta计算EMA,返回Dict格式"""
    period = int(params["period"].value)
    result = ta.ema(df["close"], length=period, talib=enable_talib)
    return {indicator_key: result.to_numpy()}


# EMA配置
ema_config = IndicatorTestConfig(
    indicator_name="ema",
    params_config={
        "ohlcv_15m": {
            "ema_0": {"period": Param(14)},
            "ema_1": {"period": Param(100)},
        },
        "ohlcv_1h": {
            "ema_0": {"period": Param(20)},
            "ema_1": {"period": Param(200)},
        },
    },
    suffixes=[],
    engine_result_extractor=ema_engine_extractor,
    pandas_ta_result_extractor=ema_pandas_ta_extractor,
)


# 测试函数
def test_accuracy(data_dict):
    """测试EMA指标计算结果与pandas-ta的一致性"""
    validate_indicator_accuracy(
        ema_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=True,
    )
