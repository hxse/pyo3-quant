# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Any

from py_entry.Test.indicators.indicator_test_template import (
    IndicatorTestConfig,
    validate_indicator_accuracy,
)
from py_entry.types import Param


# 1. 定义引擎结果提取器
def er_engine_extractor(
    indicators_df, indicator_key: str, suffixes: List[str], params: Dict
) -> Dict[str, np.ndarray]:
    """
    提取 Polars 引擎计算的 ER 结果
    """
    er = indicators_df.select(indicator_key).to_series().to_numpy()
    return {indicator_key: er}


# 2. 定义 pandas-ta 结果提取器
def er_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: List[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """
    使用 pandas_ta 计算 ER
    """
    length = int(params["length"].value)

    # 调用 pandas_ta 的 er 函数
    result = ta.er(
        close=df["close"],
        length=length,
    )

    if result is None:
        raise ValueError("pandas_ta.er returned None")

    return {indicator_key: result.to_numpy()}


# 3. 定义测试配置
config = IndicatorTestConfig(
    indicator_name="er",
    params_config={
        "ohlcv_15m": {
            "er_10": {"length": Param(10)},
            "er_20": {"length": Param(20)},
        }
    },
    suffixes=[],
    engine_result_extractor=er_engine_extractor,
    pandas_ta_result_extractor=er_pandas_ta_extractor,
)


def test_er_strict_mode(data_dict):
    """
    严格模式测试：Rust vs TA-Lib/pandas-ta (高精度对齐)
    """
    # 验证与 pandas-ta 一致
    validate_indicator_accuracy(
        config,
        data_dict,
        enable_talib=False,  # ER is pandas-ta native
        assert_mode_talib=False,
        assert_mode_pandas_ta=True,  # Must match pandas-ta
    )
