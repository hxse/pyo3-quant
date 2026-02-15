from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal, List, Any
from pyo3_quant import OptimizeMetric


class OptunaConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    n_trials: int = 100  # 总采样次数
    batch_size: int = 50  # 每批采样数 (利用 batch 并行)
    n_jobs: int = 1  # 并行 worker 数量 (-1 = 使用所有核心)
    metric: Any = OptimizeMetric.CalmarRatioRaw
    direction: Literal["maximize", "minimize"] = "maximize"
    sampler: Literal["TPE", "CMA-ES", "Random", "NSGAII"] = "TPE"
    seed: Optional[int] = None
    show_progress_bar: bool = True
    storage: Optional[str] = None  # 可选持数据库存储 (例如 "sqlite:///optuna.db")
    study_name: Optional[str] = None  # Study 名称
