from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class CallbackResult(BaseModel, Generic[T]):
    """统一的回调函数返回结构"""

    success: bool  # 是否成功
    data: Optional[T] = None  # 成功时返回的数据
    message: Optional[str] = None  # 附加信息（成功或失败都可填写）

    model_config = {"arbitrary_types_allowed": True}
