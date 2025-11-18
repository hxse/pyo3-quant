from dataclasses import dataclass, field
from typing import Optional, Type


@dataclass
class Param:
    """参数定义 - 对应 Rust Param"""

    initial_value: float
    initial_min: float
    initial_max: float
    initial_step: float

    # 运行时/当前值
    # 使用 field(init=False) 避免它们出现在 __init__ 中，且清楚地表明它们是在 post_init 中设置的。
    value: float = field(init=False)
    min: float = field(init=False)
    max: float = field(init=False)
    step: float = field(init=False)

    optimize: bool = False  # 是否开启参数优化
    log_scale: bool = False  # 是否开启对数分布

    def __post_init__(self):
        """执行验证和运行时属性的初始化。"""
        # 特例检查：(0, 0, 0, 0) 视为特例，跳过验证逻辑
        if (self.initial_value == 0.0 and
            self.initial_min == 0.0 and
            self.initial_max == 0.0 and
            self.initial_step == 0.0):
            # 直接初始化运行时属性，不执行验证
            self.value = 0.0
            self.min = 0.0
            self.max = 0.0
            self.step = 0.0
            # 特例情况下强制设置 optimize 为 false
            self.optimize = False
            return

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

        # 2. 警告检查：步长是否超出了范围
        if self.initial_step > range_diff:
            print(
                f"Warning: initial_step ({self.initial_step}) is larger than the parameter range ({range_diff}). "
                f"Optimization will not function correctly and will likely only test one point."
            )

        # 3. 致命错误检查：初始值在范围内
        if not (self.initial_min <= self.initial_value <= self.initial_max):
            raise ValueError(
                f"Validation Error: initial_value ({self.initial_value}) is outside the defined range [{self.initial_min}, {self.initial_max}]."
            )

        # 初始化运行时属性
        self.value = self.initial_value
        self.min = self.initial_min
        self.max = self.initial_max
        self.step = self.initial_step

    @classmethod
    def create(
        cls: Type["Param"],  # 使用 Type['Param'] 指向类本身
        initial_value: int | float,  # 展开 T
        initial_min: Optional[int | float] = None,  # 展开 T
        initial_max: Optional[int | float] = None,  # 展开 T
        initial_step: Optional[int | float] = None,  # 展开 T
        optimize: bool = False,  # 是否开启参数优化
        log_scale: bool = False,  # 是否开启对数分布
    ) -> "Param":  # 返回类型使用 'Param'
        """
        工厂方法：应用默认逻辑创建 Param 实例。
        """
        # 检查特例：(0, 0, 0, 0) 视为特例，所有参数设为0，optimize为false
        if (
            float(initial_value) == 0.0
            and (initial_min is None or float(initial_min) == 0.0)
            and (initial_max is None or float(initial_max) == 0.0)
            and (initial_step is None or float(initial_step) == 0.0)
        ):
            return cls(
                initial_value=0.0,
                initial_min=0.0,
                initial_max=0.0,
                initial_step=0.0,
                optimize=False,  # 特例情况下optimize为false
                log_scale=log_scale,
            )

        # 统一转换为 float
        initial_value_f = float(initial_value)

        # 应用默认值逻辑
        if initial_min is None:
            initial_min_f = initial_value_f / 2
        else:
            initial_min_f = float(initial_min)

        if initial_max is None:
            initial_max_f = initial_value_f * 2
        else:
            initial_max_f = float(initial_max)

        if initial_step is None:
            # 这里的逻辑保持不变，让 post_init 处理验证
            initial_step_f = (initial_max_f - initial_min_f) / 2
        else:
            initial_step_f = float(initial_step)

        # 使用这些计算出的值创建 Param 实例
        return cls(
            initial_value=initial_value_f,
            initial_min=initial_min_f,
            initial_max=initial_max_f,
            initial_step=initial_step_f,
            optimize=optimize,
            log_scale=log_scale,
        )
