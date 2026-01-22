from typing import List, Optional, Literal
from pydantic import BaseModel


class SignalAction(BaseModel):
    """单个交易意图（Bot 会在执行前做运行时检查）"""

    action_type: Literal[
        "close_position",
        "create_limit_order",
        "create_market_order",
        "create_stop_market_order",
        "create_take_profit_market_order",
        "cancel_all_orders",
    ]
    symbol: str
    side: Optional[Literal["long", "short"]] = None
    price: Optional[float] = None


class SignalState(BaseModel):
    """解析器返回的交易意图（不是完整执行指令）"""

    actions: List[SignalAction]
    has_exit: bool = False
