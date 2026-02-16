import io
from pathlib import Path
from typing import Any
from typing import List
from typing import Tuple

from py_entry.io._converters_serialization import dumps_json_bytes
from py_entry.io.configs import ParquetCompression
from py_entry.types import BacktestSummary


def _dataframe_to_buffer(
    df: Any,
    dataframe_format: str,
    parquet_compression: ParquetCompression,
) -> io.BytesIO:
    """将 DataFrame 统一写入 BytesIO。"""
    buf = io.BytesIO()
    if dataframe_format == "csv":
        df.write_csv(buf)
    else:
        df.write_parquet(buf, compression=parquet_compression)
    return buf


def convert_backtest_result_to_buffers(
    result: BacktestSummary,
    dataframe_format: str,
    parquet_compression: ParquetCompression,
) -> List[Tuple[Path, io.BytesIO]]:
    """将单个回测结果转换为 buffer 列表。"""
    data_list: list[tuple[Path, io.BytesIO]] = []

    # performance (dict -> json)
    if result.performance:
        data_list.append(
            (Path("performance.json"), io.BytesIO(dumps_json_bytes(result.performance)))
        )

    # indicators (dict[str, DataFrame])
    if result.indicators:
        for key, df in result.indicators.items():
            buf = _dataframe_to_buffer(df, dataframe_format, parquet_compression)
            data_list.append((Path(f"indicators_{key}.{dataframe_format}"), buf))

    # signals (DataFrame)
    if result.signals is not None:
        buf = _dataframe_to_buffer(
            result.signals, dataframe_format, parquet_compression
        )
        data_list.append((Path(f"signals.{dataframe_format}"), buf))

    # backtest_result (DataFrame)
    if result.backtest_result is not None:
        buf = _dataframe_to_buffer(
            result.backtest_result, dataframe_format, parquet_compression
        )
        data_list.append((Path(f"backtest_result.{dataframe_format}"), buf))

    return data_list
