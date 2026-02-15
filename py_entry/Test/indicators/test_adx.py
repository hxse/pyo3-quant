from typing import Dict, Any
import numpy as np
import pandas as pd
import pandas_ta as ta
import polars as pl

from py_entry.types import Param
from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    validate_indicator_accuracy,
)


# ADX引擎提取器
def adx_engine_extractor(
    indicators_df: pl.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict,
) -> Dict[str, np.ndarray]:
    result = {}
    for suffix in suffixes:
        col_name = f"{indicator_key}_{suffix}"
        result[col_name] = indicators_df[col_name].to_numpy()
    return result


# ADX pandas_ta提取器
def adx_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    period = int(params["period"].value)
    adxr_length = int(params["adxr_length"].value)

    adx_df = ta.adx(
        df["high"],
        df["low"],
        df["close"],
        length=period,
        adxr_length=adxr_length,
        talib=enable_talib,
    )

    col_name_map = {}
    for ta_key, custom_suffix in zip(["ADX", "ADXR", "DMP", "DMN"], suffixes):
        if ta_key == "ADXR":
            pandas_ta_col = f"{ta_key}_{period}_{adxr_length}"
        else:
            pandas_ta_col = f"{ta_key}_{period}"

        col_name_map[pandas_ta_col] = f"{indicator_key}_{custom_suffix}"

    result = {}
    for ta_col, custom_col in col_name_map.items():
        result[custom_col] = adx_df[ta_col].to_numpy()

    return result


# ADX配置
adx_config = IndicatorTestConfig(
    indicator_name="adx",
    params_config={
        "ohlcv_15m": {
            "adx_0": {
                "period": Param(14),
                "adxr_length": Param(2),
            },
            "adx_1": {
                "period": Param(20),
                "adxr_length": Param(4),
            },
        },
        "ohlcv_1h": {
            "adx_0": {
                "period": Param(20),
                "adxr_length": Param(10),
            },
            "adx_1": {
                "period": Param(50),
                "adxr_length": Param(20),
            },
        },
    },
    suffixes=["adx", "adxr", "plus_dm", "minus_dm"],
    engine_result_extractor=adx_engine_extractor,
    pandas_ta_result_extractor=adx_pandas_ta_extractor,
    tolerance_customizer=None,  # 任务中未提及自定义容差，使用默认
)


# 测试函数
def test_accuracy(data_dict):
    """测试ADX指标计算结果与pandas-ta talib模式的一致性"""
    validate_indicator_accuracy(
        adx_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=False,
    )
