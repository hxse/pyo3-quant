from Test.utils.over_constants import numba_config


from src.utils.mock_data import get_mock_data


import pandas as pd
import pytest


np_float = numba_config["np"]["float"]

# 创建一次模拟数据，供所有 fixture 使用
mock_data = get_mock_data(1000, "15m")


@pytest.fixture(scope="module")
def np_data_mock():
    """
    将模拟数据转换为 NumPy 格式并提供。
    """
    return mock_data


@pytest.fixture(scope="module")
def df_data_mock():
    """
    将模拟数据转换为 pandas.DataFrame 格式并提供。
    """
    df = pd.DataFrame(mock_data)

    df.rename(
        columns={0: "time", 1: "open", 2: "high", 3: "low", 4: "close", 5: "volume"},
        inplace=True,
    )
    return df
