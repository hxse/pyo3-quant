"""报告 JSON 输出工具。"""

from __future__ import annotations

import json
import math
from typing import Any


def _to_json_safe(value: Any) -> Any:
    """将报告对象转换为严格 JSON 兼容结构。"""

    if isinstance(value, float):
        if math.isfinite(value):
            return value
        # 中文注释：统一将非有限浮点映射为 null，避免下游数值比较时出现字符串类型污染。
        return None
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    return value


def dump_report(payload: dict[str, Any]) -> str:
    """序列化报告，遇到非有限浮点时先清洗再严格输出。"""

    safe_payload = _to_json_safe(payload)
    return json.dumps(
        safe_payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
