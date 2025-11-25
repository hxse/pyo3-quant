"""将回测结果转换为不同格式的buffer"""

import io
import json
from pathlib import Path
from typing import List, Tuple

from py_entry.data_conversion.types import BacktestSummary


def convert_backtest_results_to_buffers(
    results: list[BacktestSummary],
    dataframe_format: str = "csv",
) -> List[Tuple[Path, io.BytesIO]]:
    """将回测结果转换为buffer列表，用于保存或上传。

    Args:
        results: 回测结果列表
        dataframe_format: DataFrame格式，"csv"或"parquet"

    Returns:
        包含(路径, BytesIO)元组的列表
    """
    data_list = []

    for idx, summary in enumerate(results):
        # 如果有多个结果，添加子目录前缀
        prefix = f"run_{idx}/" if len(results) > 1 else ""

        # Performance (dict -> JSON)
        if summary.performance:
            json_bytes = json.dumps(
                summary.performance, indent=2, ensure_ascii=False
            ).encode("utf-8")
            data_list.append(
                (Path(f"{prefix}performance.json"), io.BytesIO(json_bytes))
            )

        # Indicators (dict[str, DataFrame])
        if summary.indicators:
            for key, df in summary.indicators.items():
                buf = io.BytesIO()
                if dataframe_format == "csv":
                    df.write_csv(buf)
                else:
                    df.write_parquet(buf)
                data_list.append(
                    (Path(f"{prefix}indicators_{key}.{dataframe_format}"), buf)
                )

        # Signals (DataFrame)
        if summary.signals is not None:
            buf = io.BytesIO()
            if dataframe_format == "csv":
                summary.signals.write_csv(buf)
            else:
                summary.signals.write_parquet(buf)
            data_list.append((Path(f"{prefix}signals.{dataframe_format}"), buf))

        # Backtest Result (DataFrame)
        if summary.backtest_result is not None:
            buf = io.BytesIO()
            if dataframe_format == "csv":
                summary.backtest_result.write_csv(buf)
            else:
                summary.backtest_result.write_parquet(buf)
            data_list.append((Path(f"{prefix}backtest_result.{dataframe_format}"), buf))

    return data_list
