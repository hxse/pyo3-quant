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


# PSAR引擎提取器
def psar_engine_extractor(
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


# PSAR pandas_ta提取器
def psar_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: list[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    af0 = float(params["af0"].value)
    af_step = float(params["af_step"].value)
    max_af = float(params["max_af"].value)

    # pandas_ta使用af参数名而不是af_step
    psar_df = ta.psar(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        af0=af0,
        af=af_step,
        max_af=max_af,
        talib=enable_talib,
    )

    _props = f"_{af0}_{max_af}"

    # 根据pandas-ta的命名规则构建精确的列名
    pandas_ta_col_names = {
        "long": f"PSARl{_props}",
        "short": f"PSARs{_props}",
        "af": f"PSARaf{_props}",
        "reversal": f"PSARr{_props}",
    }

    result = {}
    for suffix in suffixes:
        col_name_ta = pandas_ta_col_names.get(suffix)
        if col_name_ta is None or col_name_ta not in psar_df.columns:
            raise ValueError(
                f"Could not find pandas_ta PSAR column for suffix: {suffix} with expected name {col_name_ta}"
            )
        col_name_custom = f"{indicator_key}_{suffix}"
        result[col_name_custom] = psar_df[col_name_ta].to_numpy()

    return result


# PSAR配置
psar_config = IndicatorTestConfig(
    indicator_name="psar",
    params_config={
        "ohlcv": [
            # timeframe 0
            {
                "psar_0": {
                    "af0": create_param(0.02),
                    "af_step": create_param(0.02),
                    "max_af": create_param(0.2),
                },
                "psar_1": {
                    "af0": create_param(0.03),
                    "af_step": create_param(0.03),
                    "max_af": create_param(0.3),
                },
            },
            # timeframe 1
            {
                "psar_0": {
                    "af0": create_param(0.01),
                    "af_step": create_param(0.01),
                    "max_af": create_param(0.15),
                },
                "psar_1": {
                    "af0": create_param(0.025),
                    "af_step": create_param(0.025),
                    "max_af": create_param(0.25),
                },
            },
        ]
    },
    suffixes=["long", "short", "af", "reversal"],
    engine_result_extractor=psar_engine_extractor,
    pandas_ta_result_extractor=psar_pandas_ta_extractor,
)


# 测试函数
def test_accuracy(data_dict):
    """测试PSAR指标计算结果与pandas-ta的一致性"""
    _test_indicator_accuracy(
        psar_config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,
        assert_mode_pandas_ta=True,
    )
