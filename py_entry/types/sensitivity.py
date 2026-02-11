from typing import Optional, Literal, List, Dict
from pydantic import BaseModel, Field, ConfigDict

from .inputs.optimizer import OptimizeMetric


class SensitivityConfig(BaseModel):
    """敏感性测试配置

    对应 Rust 端的 SensitivityConfig
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    jitter_ratio: float = Field(0.05, description="抖动比例 (例如 0.05 代表 +/- 5%)")
    n_samples: int = Field(100, description="采样次数")
    distribution: Literal["uniform", "normal"] = Field(
        "uniform", description="分布类型"
    )
    seed: Optional[int] = Field(None, description="随机种子 (保证可复现)")
    metric: OptimizeMetric = Field(
        OptimizeMetric.CalmarRatioRaw, description="评价指标"
    )


class SensitivitySample(BaseModel):
    """单个样本的测试结果"""

    values: List[float] = Field(..., description="采样后的参数值")
    metric_value: float = Field(..., description="目标指标值")
    all_metrics: Dict[str, float] = Field(..., description="所有性能指标")


class SensitivityResult(BaseModel):
    """敏感性测试总结果"""

    target_metric: str = Field(..., description="目标指标名称")
    original_value: float = Field(..., description="原始性能指标值")
    samples: List[SensitivitySample] = Field(..., description="采样样本列表")

    # 统计量
    mean: float = Field(..., description="均值")
    std: float = Field(..., description="标准差")
    min: float = Field(..., description="最小值")
    max: float = Field(..., description="最大值")
    median: float = Field(..., description="中位数")
    cv: float = Field(..., description="变异系数 (std / mean)")
