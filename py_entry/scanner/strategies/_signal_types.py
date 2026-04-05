from typing import Literal, Any, TypedDict, NotRequired

from pydantic import BaseModel


class StrategySignal(BaseModel):
    """策略信号 - 策略函数的统一返回值"""

    # === 核心信号 ===
    strategy_name: str  # 策略名称（如 "trend", "reversal", "momentum"）
    symbol: str  # 扫描品种代码 (如 KQ.m@DCE.l)
    real_symbol: str = ""  # 实际主力合约代码 (如 DCE.i2505)，如果为空则未定义
    direction: Literal["long", "short", "none"]  # 方向

    # === 信号详情 ===
    trigger: str  # 触发信号简述（如 "15m close x> EMA"）

    # === 可展示信息 (给人看的) ===
    summary: str  # 一句话总结（如 "甲醇 做空 | 四周期共振"）
    detail_lines: list[str]  # 详细信息（每行一个字符串）

    # === 警告/提示 (可选) ===
    warnings: list[str] = []  # 警告信息列表

    # === 附加数据 (机读用) ===
    metadata: dict[str, Any] = {}  # 附加数据，供程序化处理

    def to_display_string(self, index: int | None = None) -> str:
        """
        生成展示用的多行字符串 (Console/Telegram 通用)
        Args:
            index: 如果提供，会在第一行前加序号 (如 "1. ")
        """
        symbol_display = self.symbol
        if self.real_symbol and self.real_symbol != self.symbol:
            symbol_display = f"{self.symbol} | {self.real_symbol}"

        direction_map = {"long": "做多", "short": "做空", "none": "观察"}
        dir_str = direction_map.get(self.direction, self.direction)

        prefix = f"{index}. " if index is not None else ""
        header = f"{prefix}{symbol_display} | {self.strategy_name} | {dir_str}"

        lines = [header]
        lines.append(f"  - 触发: {self.trigger}")

        if self.detail_lines:
            details_text = " ".join(self.detail_lines)
            lines.append(f"  - 详情: {details_text}")

        if self.warnings:
            lines.append(f"  - ⚠️ {' '.join(self.warnings)}")

        return "\n".join(lines)


class StrategyCheckResult(TypedDict):
    """策略内部检查结果的标准返回结构"""

    is_bullish: bool
    is_bearish: bool
    detail: str
    price: float
    trigger: NotRequired[str]
    details: NotRequired[list[str]]
