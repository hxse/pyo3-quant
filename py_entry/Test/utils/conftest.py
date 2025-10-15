import pandas as pd
import pytest
from py_entry.data_conversion.helpers.data_generator import generate_data_dict


@pytest.fixture(scope="module")
def data_dict():
    timeframes = ["15m", "1h"]
    data = generate_data_dict(
        timeframes=timeframes, start_time=1735689600000, num_bars=5000
    )
    return (timeframes, data)
