"""参数定义"""

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
        self.value = self.initial_value
        self.min = self.initial_min
        self.max = self.initial_max
        self.step = self.initial_step
