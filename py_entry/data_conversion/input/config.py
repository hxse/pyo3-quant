"""回测配置"""

from dataclasses import dataclass


@dataclass
class EngineSettings:
    """回测配置 - 对应 Rust ProcessedConfig"""

    is_only_performance: bool = False
