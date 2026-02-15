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
def cci_engine_extractor(
    indicators_df, indicator_key: str, suffixes: List[str], params: Dict
) -> Dict[str, np.ndarray]:
    """
    提取 Polars 引擎计算的 CCI 结果
    """
    # 只需要提取 indicator_key 这一列 (例如 "cci_14")
    cci = indicators_df.select(indicator_key).to_series().to_numpy()
    return {indicator_key: cci}


# 2. 定义 pandas-ta 结果提取器
def cci_pandas_ta_extractor(
    df: pd.DataFrame,
    indicator_key: str,
    suffixes: List[str],
    params: Dict[str, Any],
    enable_talib: bool,
) -> Dict[str, np.ndarray]:
    """
    使用 pandas_ta 计算 CCI
    """
    period = int(params["period"].value)

    # 注意：我们的 Rust 实现是对齐 TA-Lib 的
    # 所以无论 enable_talib 是 True 還是 False，我们都期望对齐 TA-Lib
    # 但为了测试框架的兼容性，这里还是透传 enable_talib

    # 强制让 pandas_ta 使用与 Rust 一致的逻辑
    # 如果 enable_talib=False，pandas-ta 算出来会和 Rust 不一致 (正如我们发现的 BUG)
    # 所以这里我们对于 "预期相同" 的测试，其实主要是针对 talib=True 的情况

    result = ta.cci(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=period,
        c=0.015,
        talib=enable_talib,  # 关键：透传
    )

    # pandas-ta 返回的 Series 名类似于 "CCI_14_0.015"
    # 我们直接取 result
    if result is None:
        raise ValueError("pandas_ta returned None")

    return {indicator_key: result.to_numpy()}


config = IndicatorTestConfig(
    indicator_name="cci",
    params_config={
        "ohlcv_15m": {
            "cci_14": {"period": Param(14)},
            "cci_50": {"period": Param(50)},
        }
    },
    suffixes=[],
    engine_result_extractor=cci_engine_extractor,
    pandas_ta_result_extractor=cci_pandas_ta_extractor,
)


def test_cci_strict_mode(data_dict):
    """
    严格模式测试：Rust vs TA-Lib (高精度对齐)
    """
    # 1. 验证与 TA-Lib (enable_talib=True) 一致
    print("\nExecuting Test: Rust vs TA-Lib (Should Match)")
    validate_indicator_accuracy(
        config,
        data_dict,
        enable_talib=True,
        assert_mode_talib=True,  # 必须一致
        assert_mode_pandas_ta=False,  # 忽略纯 pandas 模式的比对结果
    )
