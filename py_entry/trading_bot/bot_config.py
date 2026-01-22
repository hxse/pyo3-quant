from typing import Literal, Callable, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class BotConfig(BaseModel):
    """交易机器人配置"""

    loop_interval_sec: float = Field(default=1.0, description="检查循环间隔（秒）")
    log_level: str = Field(default="INFO", description="loguru 日志级别")
    entry_order_type: Literal["limit", "market"] = Field(
        default="limit", description="进场订单类型"
    )
    enable_aggregation: bool = Field(
        default=False, description="启用多策略聚合（当前版本不支持）"
    )

    model_config = {"arbitrary_types_allowed": True}
