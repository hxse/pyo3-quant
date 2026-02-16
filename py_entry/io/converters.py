"""将回测结果转换为不同格式的 buffer。"""

from py_entry.io._converters_bundle import convert_backtest_data_to_buffers
from py_entry.io._converters_result import convert_backtest_result_to_buffers
from py_entry.io._converters_serialization import convert_to_serializable
from py_entry.io.configs import ParquetCompression

__all__ = [
    "convert_to_serializable",
    "convert_backtest_result_to_buffers",
    "convert_backtest_data_to_buffers",
    "ParquetCompression",
]
