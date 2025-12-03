"""将回测结果转换为不同格式的buffer"""

import io
import json
from pathlib import Path
from typing import List, Tuple, Optional

from py_entry.data_conversion.types import (
    BacktestSummary,
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
)


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


def convert_all_backtest_data_to_buffers(
    data_dict: Optional[DataContainer],
    param_set: Optional[ParamContainer],
    template_config: Optional[TemplateContainer],
    engine_settings: Optional[SettingContainer],
    results: list[BacktestSummary],
    dataframe_format: str = "csv",
) -> List[Tuple[Path, io.BytesIO]]:
    """将所有回测数据（包括配置和结果）转换为buffer列表，用于保存或上传。

    Args:
        data_dict: 数据容器
        param_set: 参数容器
        template_config: 模板配置容器
        engine_settings: 引擎设置容器
        results: 回测结果列表
        dataframe_format: DataFrame格式，"csv"或"parquet"

    Returns:
        包含(路径, BytesIO)元组的列表
    """
    data_list = []

    # 1. 转换回测结果（使用现有函数）
    result_buffers = convert_backtest_results_to_buffers(results, dataframe_format)
    prefixed_result_buffers = [
        (Path("backtest_results") / path, buffer) for path, buffer in result_buffers
    ]
    data_list.extend(prefixed_result_buffers)

    # 2. 转换数据字典
    if data_dict is not None:
        # mapping (DataFrame)
        if data_dict.mapping is not None:
            buf = io.BytesIO()
            if dataframe_format == "csv":
                data_dict.mapping.write_csv(buf)
            else:
                data_dict.mapping.write_parquet(buf)
            data_list.append((Path("data_dict/mapping.csv"), buf))

        # skip_mask (Series)
        if data_dict.skip_mask is not None:
            buf = io.BytesIO()
            skip_mask_df = data_dict.skip_mask.to_frame()
            if dataframe_format == "csv":
                skip_mask_df.write_csv(buf)
            else:
                skip_mask_df.write_parquet(buf)
            data_list.append((Path("data_dict/skip_mask.csv"), buf))

        # skip_mapping (dict)
        if data_dict.skip_mapping is not None:
            json_bytes = json.dumps(
                data_dict.skip_mapping, indent=2, ensure_ascii=False
            ).encode("utf-8")
            data_list.append(
                (Path("data_dict/skip_mapping.json"), io.BytesIO(json_bytes))
            )

        # source (dict[str, DataFrame])
        if data_dict.source is not None:
            for key, df in data_dict.source.items():
                buf = io.BytesIO()
                if dataframe_format == "csv":
                    df.write_csv(buf)
                else:
                    df.write_parquet(buf)
                data_list.append(
                    (Path(f"data_dict/source_{key}.{dataframe_format}"), buf)
                )

        # BaseDataKey (str)
        if data_dict.BaseDataKey is not None:
            json_bytes = json.dumps(
                {"BaseDataKey": data_dict.BaseDataKey}, indent=2, ensure_ascii=False
            ).encode("utf-8")
            data_list.append(
                (Path("data_dict/base_data_key.json"), io.BytesIO(json_bytes))
            )

    # 3. 转换参数集
    if param_set is not None:
        param_list = []
        for i, single_param in enumerate(param_set):
            param_dict = {
                "indicators": single_param.indicators,
                "signal": single_param.signal,
                "backtest": single_param.backtest.__dict__,
                "performance": {
                    "metrics": [
                        metric.value for metric in single_param.performance.metrics
                    ]
                },
            }
            param_list.append(param_dict)

        json_bytes = json.dumps(
            param_list, indent=2, ensure_ascii=False, default=str
        ).encode("utf-8")
        data_list.append((Path("param_set/param_set.json"), io.BytesIO(json_bytes)))

    # 4. 转换模板配置
    if template_config is not None:
        template_dict = {
            "name": template_config.signal.name,
            "enter_long": template_config.signal.enter_long,
            "exit_long": template_config.signal.exit_long,
            "enter_short": template_config.signal.enter_short,
            "exit_short": template_config.signal.exit_short,
        }
        json_bytes = json.dumps(
            template_dict, indent=2, ensure_ascii=False, default=str
        ).encode("utf-8")
        data_list.append(
            (Path("template_config/template_config.json"), io.BytesIO(json_bytes))
        )

    # 5. 转换引擎设置
    if engine_settings is not None:
        settings_dict = {
            "execution_stage": engine_settings.execution_stage.value,
            "return_only_final": engine_settings.return_only_final,
        }
        json_bytes = json.dumps(
            settings_dict, indent=2, ensure_ascii=False, default=str
        ).encode("utf-8")
        data_list.append(
            (Path("engine_settings/engine_settings.json"), io.BytesIO(json_bytes))
        )

    return data_list
