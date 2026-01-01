from typing import List, Tuple, Optional


def sort_timeframe_keys(keys: List[str], base_key: str) -> List[str]:
    """
    对时间周期键进行排序

    Args:
        keys: 所有数据源键
        base_key: 基准键 (如 "ohlcv_15m")

    Returns:
        排序后的键列表，基准键在前，同前缀按时间周期升序排列
    """
    # 提取基准键的前缀 (如 "ohlcv")
    prefix = base_key.rsplit("_", 1)[0] if "_" in base_key else base_key

    # 筛选同前缀的键
    same_prefix = [k for k in keys if k.startswith(prefix + "_")]
    other = [k for k in keys if k not in same_prefix]

    # 时间周期排序权重
    timeframe_order = {"m": 0, "h": 1, "d": 2, "w": 3, "M": 4}

    def parse_timeframe(key: str) -> Tuple[int, int]:
        # 提取时间周期部分 (如 "15m" -> (0, 15))
        suffix = key.rsplit("_", 1)[-1]
        for unit, weight in timeframe_order.items():
            if suffix.endswith(unit):
                try:
                    num = int(suffix[: -len(unit)])
                    return (weight, num)
                except ValueError:
                    pass
        return (999, 0)  # 无法解析的放最后

    # 排序：基准键优先，其余按时间周期升序
    sorted_same = sorted(same_prefix, key=parse_timeframe)
    if base_key in sorted_same:
        sorted_same.remove(base_key)
        sorted_same.insert(0, base_key)

    return sorted_same + other


def parse_indicator_name(
    name: str, indicator_settings: dict
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    解析指标名称

    Args:
        name: 指标列名 (如 "bbands_bandwidth", "sma_0", "rsi")
        indicator_settings: 指标配置字典

    Returns:
        (base_type, identifier, component)
        - base_type: 指标类型 (如 "bbands", "sma", "rsi")
        - identifier: 标识符 (如 "0", "1")
        - component: 组件名 (如 "bandwidth", "upper")
    """
    parts = name.split("_")
    if not parts:
        return (name, None, None)

    base_type = parts[0]
    component = None
    identifier = None

    # 检查最后一部分是否是组件
    if base_type in indicator_settings:
        settings = indicator_settings[base_type]
        if hasattr(settings, "components") and settings.components and len(parts) > 1:
            # 检查最后一部分是否匹配组件
            last_part = parts[-1]
            if last_part in settings.components:
                component = last_part
                # 中间部分是标识符
                if len(parts) > 2:
                    identifier = "_".join(parts[1:-1])
            else:
                # 不是组件，全部算标识符
                identifier = "_".join(parts[1:])
        elif len(parts) > 1:
            identifier = "_".join(parts[1:])

    return (base_type, identifier, component)
