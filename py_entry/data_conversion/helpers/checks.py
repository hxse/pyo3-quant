from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar, Union

# 使用 TypeVar 来表示任意的 dataclass 类型
# TypeVar('T') 约束了 T 必须是类型，但没有限制它必须是 dataclass，
# 因此我们依靠运行时 is_dataclass 检查来保证安全。
T = TypeVar("T")


def validate_no_none_fields(instance: T) -> None:
    """
    检查任意 dataclass 实例的所有顶层字段是否为 None。
    如果发现任何 None 值，则抛出 ValueError。

    Args:
        instance: 要检查的 dataclass 实例。

    Raises:
        TypeError: 如果传入的不是一个 dataclass 实例。
        ValueError: 如果发现任何字段的值为 None。
    """
    # 1. 确保传入的是一个 dataclass 实例
    if not is_dataclass(instance):
        # 使用 isinstance(instance, type) 可以区分实例和类，但为了通用性，is_dataclass 更好。
        raise TypeError(
            f"配置错误：期望传入一个 dataclass 实例，但收到 {type(instance)}。"
        )

    # 2. 将 dataclass 转换为字典，以便遍历字段及其值
    data = asdict(instance)

    # 3. 遍历字典，检查值是否为 None
    for field_name, field_value in data.items():
        if field_value is None:
            # 发现 None，立即抛出错误
            raise ValueError(
                f"配置错误：{type(instance).__name__} 实例的字段 '{field_name}' 的值不能是 None。请检查该字段的来源。"
            )

    # print(f"✅ {type(instance).__name__} 验证成功，没有发现 None 值。")
