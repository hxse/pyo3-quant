from pydantic import BaseModel
from .optimizer import OptimizerConfig


class WalkForwardConfig(BaseModel):
    train_ratio: float = 0.60
    test_ratio: float = 0.20
    step_ratio: float = 0.10
    inherit_prior: bool = True
    optimizer_config: OptimizerConfig = OptimizerConfig()
