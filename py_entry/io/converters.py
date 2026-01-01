"""将回测结果转换为不同格式的buffer"""

import io
import json
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from typing import List, Tuple, Optional, Any
from .configs import ParquetCompression

from py_entry.types import (
    BacktestSummary,
    DataContainer,
    SingleParamSet,
    TemplateContainer,
    SettingContainer,
)

from py_entry.types import ChartConfig


def convert_to_serializable(obj: Any) -> Any:
    """递归地将对象转换为 JSON 可序列化的格式。

    支持的类型转换：
    - dataclass 对象（如 Param、SignalGroup）-> dict（过滤 None 值和不相关的字段）
    - Pydantic 模型 -> dict（过滤 None 值）
    - Enum 对象 -> value
    - dict -> 递归处理每个值
    - list -> 递归处理每个元素

    Args:
        obj: 要转换的对象

    Returns:
        转换后的对象，可被 JSON 序列化
    """
    if obj is None:
        return None

    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)

    elif is_dataclass(obj) and not isinstance(obj, type):
        # 不使用 asdict()，因为它会递归展开所有嵌套对象
        # 手动遍历字段以保留类型信息
        from dataclasses import fields

        obj_dict = {}
        for field in fields(obj):
            field_value = getattr(obj, field.name)
            obj_dict[field.name] = field_value

        # 特殊处理 SeriesItemConfig：根据 type 过滤选项字段
        if obj.__class__.__name__ == "SeriesItemConfig":
            item_type = obj_dict.get("type")

            # 定义每种类型需要保留的选项字段
            type_to_opt_map = {
                "candle": "candleOpt",
                "histogram": "histogramOpt",
                "line": "lineOpt",
                "area": "lineOpt",
                "baseline": "lineOpt",
                "bar": "lineOpt",
                "hline": "hLineOpt",
                "vline": "vLineOpt",
            }

            # 所有选项字段
            all_opt_fields = {
                "candleOpt",
                "histogramOpt",
                "lineOpt",
                "hLineOpt",
                "vLineOpt",
            }

            # 确定要保留的选项字段
            keep_opt = type_to_opt_map.get(item_type)

            # 过滤掉不需要的选项字段
            filtered_dict = {}
            for k, v in obj_dict.items():
                # 如果是选项字段
                if k in all_opt_fields:
                    # 只保留当前类型需要的选项字段（且非 None）
                    if k == keep_opt and v is not None:
                        filtered_dict[k] = convert_to_serializable(v)
                    # 其他选项字段跳过（不输出）
                else:
                    # 非选项字段，过滤 None 值
                    if v is not None:
                        filtered_dict[k] = convert_to_serializable(v)

            return filtered_dict
        else:
            # 其他 dataclass：过滤掉值为 None 的字段
            return {
                k: convert_to_serializable(v)
                for k, v in obj_dict.items()
                if v is not None
            }
    elif isinstance(obj, Enum):
        # 将 Enum 转换为其值
        return obj.value
    elif isinstance(obj, dict):
        # 递归处理字典中的每个值
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        # 递归处理列表中的每个元素
        return [convert_to_serializable(item) for item in obj]
    else:
        # 其他类型直接返回
        return obj


def convert_backtest_result_to_buffers(
    result: BacktestSummary,
    dataframe_format: str,
    parquet_compression: ParquetCompression,
) -> List[Tuple[Path, io.BytesIO]]:
    """将单个回测结果转换为buffer列表，用于保存或上传。

    Args:
        result: 单个回测结果
        dataframe_format: DataFrame格式，"csv"或"parquet"
        parquet_compression: Parquet 压缩算法，默认 "snappy"

    Returns:
        包含(路径, BytesIO)元组的列表
    """
    data_list = []

    # Performance (dict -> JSON)
    if result.performance:
        json_bytes = json.dumps(
            result.performance, indent=2, ensure_ascii=False
        ).encode("utf-8")
        data_list.append((Path("performance.json"), io.BytesIO(json_bytes)))

    # Indicators (dict[str, DataFrame])
    if result.indicators:
        for key, df in result.indicators.items():
            buf = io.BytesIO()
            if dataframe_format == "csv":
                df.write_csv(buf)
            else:
                df.write_parquet(buf, compression=parquet_compression)
            data_list.append((Path(f"indicators_{key}.{dataframe_format}"), buf))

    # Signals (DataFrame)
    if result.signals is not None:
        buf = io.BytesIO()
        if dataframe_format == "csv":
            result.signals.write_csv(buf)
        else:
            result.signals.write_parquet(buf, compression=parquet_compression)
        data_list.append((Path(f"signals.{dataframe_format}"), buf))

    # Backtest Result (DataFrame)
    if result.backtest_result is not None:
        buf = io.BytesIO()
        if dataframe_format == "csv":
            result.backtest_result.write_csv(buf)
        else:
            result.backtest_result.write_parquet(buf, compression=parquet_compression)
        data_list.append((Path(f"backtest_result.{dataframe_format}"), buf))

    return data_list


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
    """将单个回测数据（包括配置和结果）转换为buffer列表，用于保存或上传。

    Args:
        data_dict: 数据容器
        param: 单个参数集
        template_config: 模板配置容器
        engine_settings: 引擎设置容器
        result: 单个回测结果
        dataframe_format: DataFrame格式，"csv"或"parquet"
        parquet_compression: Parquet 压缩算法，默认 "snappy"
        chart_config: 图表配置对象。如果不提供，尝试自动生成。

    Returns:
        包含(路径, BytesIO)元组的列表
    """
    data_list = []

    # 1. 转换回测结果（使用现有函数）
    result_buffers = convert_backtest_result_to_buffers(
        result, dataframe_format, parquet_compression
    )
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
                data_dict.mapping.write_parquet(buf, compression=parquet_compression)
            data_list.append((Path(f"data_dict/mapping.{dataframe_format}"), buf))

        # skip_mask (DataFrame)
        if data_dict.skip_mask is not None:
            buf = io.BytesIO()
            if dataframe_format == "csv":
                data_dict.skip_mask.write_csv(buf)
            else:
                data_dict.skip_mask.write_parquet(buf, compression=parquet_compression)
            data_list.append((Path(f"data_dict/skip_mask.{dataframe_format}"), buf))

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
                    df.write_parquet(buf, compression=parquet_compression)
                data_list.append(
                    (Path(f"data_dict/source_{key}.{dataframe_format}"), buf)
                )

        # base_data_key (str)
        if data_dict.base_data_key is not None:
            json_bytes = json.dumps(
                {"base_data_key": data_dict.base_data_key}, indent=2, ensure_ascii=False
            ).encode("utf-8")
            data_list.append(
                (Path("data_dict/base_data_key.json"), io.BytesIO(json_bytes))
            )

    # 3. 转换单个参数集（删除循环）
    if param is not None:
        param_dict = {
            "indicators": convert_to_serializable(param.indicators),
            "signal": convert_to_serializable(param.signal),
            "backtest": convert_to_serializable(param.backtest),
            "performance": {
                "metrics": [metric.value for metric in param.performance.metrics]
            },
        }
        json_bytes = json.dumps(param_dict, indent=2, ensure_ascii=False).encode(
            "utf-8"
        )
        data_list.append((Path("param_set/param.json"), io.BytesIO(json_bytes)))

    # 4. 转换模板配置
    if template_config is not None:
        template_dict = {
            "entry_long": convert_to_serializable(template_config.signal.entry_long),
            "exit_long": convert_to_serializable(template_config.signal.exit_long),
            "entry_short": convert_to_serializable(template_config.signal.entry_short),
            "exit_short": convert_to_serializable(template_config.signal.exit_short),
        }
        json_bytes = json.dumps(template_dict, indent=2, ensure_ascii=False).encode(
            "utf-8"
        )
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

    # 6. ChartConfig
    # chart_config 应该已经由调用方生成
    if chart_config:
        config_dict = convert_to_serializable(chart_config)
        json_bytes = json.dumps(config_dict, indent=2, ensure_ascii=False).encode(
            "utf-8"
        )
        data_list.append((Path("chartConfig.json"), io.BytesIO(json_bytes)))

    return data_list
