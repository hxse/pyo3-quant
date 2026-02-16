import io
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

from py_entry.io._converters_result import convert_backtest_result_to_buffers
from py_entry.io._converters_serialization import convert_to_serializable
from py_entry.io._converters_serialization import dumps_json_bytes
from py_entry.io.configs import ParquetCompression
from py_entry.types import BacktestSummary
from py_entry.types import ChartConfig
from py_entry.types import DataContainer
from py_entry.types import SettingContainer
from py_entry.types import SingleParamSet
from py_entry.types import TemplateContainer


def _write_df(
    df: Any,
    dataframe_format: str,
    parquet_compression: ParquetCompression,
) -> io.BytesIO:
    """将 DataFrame 统一输出为内存 buffer。"""
    buf = io.BytesIO()
    if dataframe_format == "csv":
        df.write_csv(buf)
    else:
        df.write_parquet(buf, compression=parquet_compression)
    return buf


def convert_backtest_data_to_buffers(
    data_dict: Optional[DataContainer],
    param: SingleParamSet,
    template_config: Optional[TemplateContainer],
    engine_settings: Optional[SettingContainer],
    result: BacktestSummary,
    dataframe_format: str,
    parquet_compression: ParquetCompression,
    chart_config: Optional[ChartConfig] = None,
) -> List[Tuple[Path, io.BytesIO]]:
    """将单个回测数据（配置 + 结果）转换为 buffer 列表。"""
    data_list: list[tuple[Path, io.BytesIO]] = []

    # 1) 回测结果
    result_buffers = convert_backtest_result_to_buffers(
        result, dataframe_format, parquet_compression
    )
    data_list.extend(
        (Path("backtest_results") / path, buffer) for path, buffer in result_buffers
    )

    # 2) 数据字典
    if data_dict is not None:
        if data_dict.mapping is not None:
            data_list.append(
                (
                    Path(f"data_dict/mapping.{dataframe_format}"),
                    _write_df(data_dict.mapping, dataframe_format, parquet_compression),
                )
            )

        if data_dict.skip_mask is not None:
            data_list.append(
                (
                    Path(f"data_dict/skip_mask.{dataframe_format}"),
                    _write_df(
                        data_dict.skip_mask, dataframe_format, parquet_compression
                    ),
                )
            )

        if data_dict.skip_mapping is not None:
            data_list.append(
                (
                    Path("data_dict/skip_mapping.json"),
                    io.BytesIO(dumps_json_bytes(data_dict.skip_mapping)),
                )
            )

        if data_dict.source is not None:
            for key, df in data_dict.source.items():
                data_list.append(
                    (
                        Path(f"data_dict/source_{key}.{dataframe_format}"),
                        _write_df(df, dataframe_format, parquet_compression),
                    )
                )

        if data_dict.base_data_key is not None:
            data_list.append(
                (
                    Path("data_dict/base_data_key.json"),
                    io.BytesIO(
                        dumps_json_bytes({"base_data_key": data_dict.base_data_key})
                    ),
                )
            )

    # 3) 参数集
    if param is not None:
        param_dict = {
            "indicators": convert_to_serializable(param.indicators),
            "signal": convert_to_serializable(param.signal),
            "backtest": convert_to_serializable(param.backtest),
            "performance": {
                "metrics": [str(metric) for metric in param.performance.metrics]
            },
        }
        data_list.append(
            (Path("param_set/param.json"), io.BytesIO(dumps_json_bytes(param_dict)))
        )

    # 4) 模板配置
    if template_config is not None:
        template_dict = {
            "entry_long": convert_to_serializable(template_config.signal.entry_long),
            "exit_long": convert_to_serializable(template_config.signal.exit_long),
            "entry_short": convert_to_serializable(template_config.signal.entry_short),
            "exit_short": convert_to_serializable(template_config.signal.exit_short),
        }
        data_list.append(
            (
                Path("template_config/template_config.json"),
                io.BytesIO(dumps_json_bytes(template_dict)),
            )
        )

    # 5) 引擎设置
    if engine_settings is not None:
        settings_dict = {
            "execution_stage": convert_to_serializable(engine_settings.execution_stage),
            "return_only_final": engine_settings.return_only_final,
        }
        data_list.append(
            (
                Path("engine_settings/engine_settings.json"),
                io.BytesIO(dumps_json_bytes(settings_dict)),
            )
        )

    # 6) ChartConfig
    if chart_config:
        config_dict = convert_to_serializable(chart_config)
        data_list.append(
            (Path("chartConfig.json"), io.BytesIO(dumps_json_bytes(config_dict)))
        )

    return data_list
