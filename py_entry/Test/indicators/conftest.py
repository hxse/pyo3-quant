import pytest
from py_entry.data_conversion.helpers.data_generator import (
    generate_data_dict,
    DataGenerationParams,
)


@pytest.fixture(scope="module")
def data_dict():
    """生成指标测试所需的测试数据"""
    timeframes = ["15m", "1h"]
    simulated_data_config = DataGenerationParams(
        timeframes=timeframes, start_time=1735689600000, num_bars=5000
    )
    data = generate_data_dict(data_source=simulated_data_config)
    return data
