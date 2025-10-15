from dataclasses import dataclass, field


@dataclass
class Param:
    """参数定义 - 对应 Rust Param"""

    initial_value: float
    initial_min: float
    initial_max: float
    initial_step: float
    value: float = field(init=False)
    min: float = field(init=False)
    max: float = field(init=False)
    step: float = field(init=False)
    optimize: bool = False

    def __post_init__(self):
        # 验证逻辑
        if self.initial_max <= self.initial_min:
            raise ValueError(
                f"Validation Error: initial_max ({self.initial_max}) must be strictly greater than initial_min ({self.initial_min})."
            )
        range_diff = self.initial_max - self.initial_min

        # 1. 致命错误检查：步长必须为正数
        if self.initial_step <= 0:
            raise ValueError(
                f"Validation Error: initial_step ({self.initial_step}) must be a positive number."
            )

        # 2. 警告检查：步长是否超出了范围（非致命，但可能导致优化器行为异常）
        if self.initial_step > range_diff:
            # 这里的逻辑是：如果步长大于范围，虽然技术上能创建一个值，但优化器可能失败或只测试一个点。
            # 使用 print 警告，而不是阻止 Param 对象的创建。
            print(
                f"Warning: initial_step ({self.initial_step}) is larger than the parameter range ({range_diff}). "
                f"Optimization will not function correctly and will likely only test one point."
            )

        # 初始值也应该在 min/max 范围内，这也是一个好习惯。
        if not (self.initial_min <= self.initial_value <= self.initial_max):
            raise ValueError(
                f"Validation Error: initial_value ({self.initial_value}) is outside the defined range [{self.initial_min}, {self.initial_max}]."
            )

        # 初始化属性
        self.value = self.initial_value
        self.min = self.initial_min
        self.max = self.initial_max
        self.step = self.initial_step
