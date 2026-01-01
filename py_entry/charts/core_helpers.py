"""
图表配置生成核心辅助函数

提供用于图表配置生成流程的核心辅助函数。
"""

from typing import List, Optional, TypeVar


# 定义泛型类型变量，用于保持选项类型
T = TypeVar("T")


def get_style_option(options_list: Optional[List[T]], counter: int) -> Optional[T]:
    """
    从选项数组中获取指定索引的选项，如果超出范围则返回最后一个。

    Args:
        options_list: 选项数组（如 lineOptions, candleOptions 等）
        counter: 当前计数器值

    Returns:
        对应索引的选项对象，如果数组为空或 None 则返回 None
    """
    if not options_list:
        return None

    # 如果计数器在范围内，返回对应索引的选项
    if counter < len(options_list):
        return options_list[counter]
    else:
        # 否则重复最后一个选项
        return options_list[-1]


def init_counter(style_counters: dict[str, int], indicator_name: str) -> int:
    """
    初始化或获取指标的计数器。

    Args:
        style_counters: 计数器字典
        indicator_name: 指标名称

    Returns:
        当前计数器值
    """
    if indicator_name not in style_counters:
        style_counters[indicator_name] = 0
    return style_counters[indicator_name]


def match_indicator_columns(indicator_name: str, available_columns: set) -> list[str]:
    """
    匹配指标名称到实际的数据列名（支持多个匹配）。

    例如：indicator_name="sma" 可能匹配 ["sma_0", "sma_1", "sma_2"]

    Args:
        indicator_name: INDICATOR_LAYOUT 中定义的指标名称
        available_columns: 实际可用的列名集合

    Returns:
        匹配的列名列表（按照字母顺序排序）
    """
    matched = []

    # 直接匹配
    if indicator_name in available_columns:
        matched.append(indicator_name)
        return matched

    # 模糊匹配：查找所有以 indicator_name_ 开头的列
    # 例如 "sma" 匹配 "sma_0", "sma_1" 等
    prefix = f"{indicator_name}_"
    for col in available_columns:
        if col.startswith(prefix):
            matched.append(col)

    # 排序以保证顺序一致性
    return sorted(matched)


def match_indicator_column(
    indicator_name: str, available_columns: set
) -> Optional[str]:
    """
    匹配指标名称到实际的数据列名（只返回第一个匹配）。

    Args:
        indicator_name: INDICATOR_LAYOUT 中定义的指标名称
        available_columns: 实际可用的列名集合

    Returns:
        匹配的列名，如果没有匹配则返回 None
    """
    # 直接匹配
    if indicator_name in available_columns:
        return indicator_name

    # 尝试匹配无标识符的情况
    # 例如：indicator_name="sma" 应该匹配 "sma_0", "sma_1" 等
    # 但由于我们要求精确匹配，这里不做模糊匹配
    # 如果需要模糊匹配，可以在这里添加逻辑

    return None
