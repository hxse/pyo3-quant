from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar, Union

# 定义一个类型变量，限制为 dataclass 实例类型
T = TypeVar("T", bound=object)


def validate_no_none_fields(instance: Union[T, type[T]]) -> None:
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

    # 2. 如果传入的是类而不是实例，抛出错误
    if isinstance(instance, type):
        raise TypeError(
            f"配置错误：期望传入一个 dataclass 实例，但收到 dataclass 类 {instance.__name__}。"
        )

    # 3. 将 dataclass 转换为字典，以便遍历字段及其值
    # 现在类型检查器知道 instance 是一个实例，不是类
    data = asdict(instance)

    # 3. 遍历字典，检查值是否为 None
    for field_name, field_value in data.items():
        if field_value is None:
            # 发现 None，立即抛出错误
            raise ValueError(
                f"配置错误：{type(instance).__name__} 实例的字段 '{field_name}' 的值不能是 None。请检查该字段的来源。"
            )

    # print(f"✅ {type(instance).__name__} 验证成功，没有发现 None 值。")
