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


# BBands引擎提取器
def bbands_engine_extractor(
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


# BBands pandas_ta提取器
def bbands_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    length = int(params["length"].value)
    std = float(params["std"].value)

    bbands_df = ta.bbands(df["close"], length=length, std=std, talib=enable_talib)

    # 提取5个列
    _s = ["L", "M", "U", "B", "P"]
    result = {}
    for suffix_ta, suffix_custom in zip(_s, suffixes):
        col_name_ta = f"BB{suffix_ta}_{length}_{std}"
        col_name_custom = f"{indicator_key}_{suffix_custom}"
        result[col_name_custom] = bbands_df[col_name_ta].to_numpy()

    return result


# BBands阈值自定义函数
def bbands_tolerance_customizer(name: str) -> Dict[str, float]:
    """根据列名返回自定义阈值"""
    if "_percent" in name:
        # percent列精度要求较低
        return {"custom_rtol": 1e-3, "custom_atol": 1e-6}
    return {}


# BBands配置
bbands_config = IndicatorTestConfig(
    indicator_name="bbands",
    params_config=[
        # timeframe 0
        {
            "bbands_0": {
                "length": create_param(14),
                "std": create_param(2.0),
            },
            "bbands_1": {
                "length": create_param(20),
                "std": create_param(2.5),
            },
        },
        # timeframe 1
        {
            "bbands_0": {
                "length": create_param(20),
                "std": create_param(2.0),
            },
            "bbands_1": {
                "length": create_param(30),
                "std": create_param(3.0),
            },
        },
    ],
    suffixes=["lower", "middle", "upper", "bandwidth", "percent"],
    engine_result_extractor=bbands_engine_extractor,
    pandas_ta_result_extractor=bbands_pandas_ta_extractor,
    tolerance_customizer=bbands_tolerance_customizer,
)


# 测试函数
def test_accuracy(data_dict):
    """测试BBands指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        bbands_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=True,
    )
