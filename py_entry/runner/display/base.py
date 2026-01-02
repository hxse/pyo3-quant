"""显示模块的共享辅助函数和工具"""

import json
import time
import random
from typing import Dict, Any


def generate_unique_container_id() -> str:
    """生成唯一的容器 ID

    Returns:
        格式为 chart-dashboard-container-{timestamp}-{random} 的唯一 ID
    """
    unique_timestamp = int(time.time() * 1000)
    random_part = random.randint(0, 99999)
    return f"chart-dashboard-container-{unique_timestamp}-{random_part}"


def escape_json_for_js(data: Dict[str, Any]) -> str:
    """将 Python 字典转换为可安全嵌入 JavaScript 单引号字符串中的 JSON

    Args:
        data: 要转换的字典

    Returns:
        转义后的 JSON 字符串，可安全嵌入到 JavaScript 的单引号字符串中
    """
    config_json = json.dumps(data)
    # 转义反斜杠和单引号，以便安全地嵌入到 JavaScript 单引号字符串中
    config_str = config_json.replace("\\", "\\\\").replace("'", "\\'")
    return config_str


def sanitize_id_for_js_function(container_id: str) -> str:
    """将容器 ID 转换为有效的 JavaScript 函数名部分

    Args:
        container_id: 容器 ID

    Returns:
        可用于 JavaScript 函数名的字符串（将 - 替换为 _）
    """
    return container_id.replace("-", "_")
