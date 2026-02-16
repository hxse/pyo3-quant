import json
from dataclasses import is_dataclass
from enum import Enum
from typing import Any

from py_entry.types import BacktestParams
from py_entry.types import ExecutionStage
from py_entry.types import LogicOp
from py_entry.types import Param
from py_entry.types import ParamType
from py_entry.types import SignalGroup
from py_entry.types import SignalTemplate


def convert_to_serializable(obj: Any) -> Any:
    """递归地将对象转换为 JSON 可序列化格式。"""
    if obj is None:
        return None

    # Pydantic 模型优先走 model_dump
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)

    # dataclass：手动字段遍历，保留对嵌套对象的控制
    if is_dataclass(obj) and not isinstance(obj, type):
        from dataclasses import fields

        obj_dict: dict[str, Any] = {}
        for field in fields(obj):
            obj_dict[field.name] = getattr(obj, field.name)

        # 特殊处理 SeriesItemConfig：按 type 过滤选项字段
        if obj.__class__.__name__ == "SeriesItemConfig":
            item_type = obj_dict.get("type")
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
            all_opt_fields = {
                "candleOpt",
                "histogramOpt",
                "lineOpt",
                "hLineOpt",
                "vLineOpt",
            }
            keep_opt = type_to_opt_map.get(item_type)

            filtered_dict: dict[str, Any] = {}
            for k, v in obj_dict.items():
                if k in all_opt_fields:
                    if k == keep_opt and v is not None:
                        filtered_dict[k] = convert_to_serializable(v)
                elif v is not None:
                    filtered_dict[k] = convert_to_serializable(v)
            return filtered_dict

        return {
            k: convert_to_serializable(v) for k, v in obj_dict.items() if v is not None
        }

    # Param 显式展开，保证前端配置字段稳定
    if isinstance(obj, Param):
        return {
            "value": obj.value,
            "min": obj.min,
            "max": obj.max,
            "step": obj.step,
            "optimize": obj.optimize,
            "log_scale": obj.log_scale,
            "dtype": str(obj.dtype),
        }

    # PyO3 枚举统一转字符串
    if isinstance(
        obj, (ParamType, LogicOp, ExecutionStage)
    ) or obj.__class__.__name__ in ("LogicOp", "ExecutionStage"):
        return str(obj)

    # BacktestParams 显式按白名单输出
    if isinstance(obj, BacktestParams):
        backtest_fields = [
            "sl_pct",
            "tp_pct",
            "tsl_pct",
            "sl_atr",
            "tp_atr",
            "tsl_atr",
            "atr_period",
            "tsl_psar_af0",
            "tsl_psar_af_step",
            "tsl_psar_max_af",
            "tsl_atr_tight",
            "sl_exit_in_bar",
            "tp_exit_in_bar",
            "sl_trigger_mode",
            "tp_trigger_mode",
            "tsl_trigger_mode",
            "sl_anchor_mode",
            "tp_anchor_mode",
            "tsl_anchor_mode",
            "initial_capital",
            "fee_fixed",
            "fee_pct",
        ]
        return {
            k: convert_to_serializable(getattr(obj, k))
            for k in backtest_fields
            if getattr(obj, k) is not None
        }

    if isinstance(obj, SignalGroup):
        return {
            "logic": convert_to_serializable(obj.logic),
            "comparisons": obj.comparisons,
            "sub_groups": convert_to_serializable(obj.sub_groups),
        }

    if isinstance(obj, SignalTemplate):
        return {
            k: convert_to_serializable(getattr(obj, k))
            for k in ["entry_long", "exit_long", "entry_short", "exit_short"]
            if getattr(obj, k) is not None
        }

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]

    return obj


def dumps_json_bytes(data: Any) -> bytes:
    """统一 JSON 序列化字节输出格式。"""
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
