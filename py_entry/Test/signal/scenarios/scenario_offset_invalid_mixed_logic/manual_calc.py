"""场景: 无效的混合逻辑偏移 - 手写计算

这个场景预期会失败，因为混合了AND和OR逻辑
手动计算函数不会被调用，因为解析阶段就会报错
"""

import polars as pl
from py_entry.Test.signal.utils import create_signal_dataframe


def calculate_signals(
    data_container,
    signal_params,
    indicators_15m,
    indicators_1h,
    indicators_4h,
    ohlcv_15m,
    ohlcv_1h,
    ohlcv_4h,
) -> pl.DataFrame:
    """
    这个函数不应该被调用，因为解析阶段就会报错
    """
    # 这个场景预期在解析阶段就失败，所以这里返回空DataFrame
    # 实际测试中会捕获解析错误
    length = len(ohlcv_15m)
    return pl.DataFrame(
        {
            "enter_long": pl.Series([False] * length),
            "exit_long": pl.Series([False] * length),
            "enter_short": pl.Series([False] * length),
            "exit_short": pl.Series([False] * length),
        }
    )
