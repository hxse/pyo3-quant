import pytest
from py_entry.data_conversion.helpers.data_generator import (
    generate_data_dict,
    DataGenerationParams,
)


@pytest.fixture(scope="module")
def data_dict():
    timeframes = ["15m", "1h"]
    simulated_data_config = DataGenerationParams(
        timeframes=timeframes, start_time=1735689600000, num_bars=5000
    )
    data = generate_data_dict(simulated_data_config=simulated_data_config)
    return (timeframes, data)
