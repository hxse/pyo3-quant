from dataclasses import dataclass
from typing import Optional
import polars as pl


@dataclass
class BacktestSummary:
    """回测结果摘要数据类

    从Rust端返回的字典转换为强类型dataclass,提供更好的类型提示和IDE支持。

    Attributes:
        performance: 性能指标字典,键为指标名称,值为指标数值
        indicators: 指标DataFrame列表
        signals: 交易信号DataFrame
        backtest_result: 回测结果DataFrame
    """

    performance: Optional[dict[str, float]] = None
    indicators: Optional[list[pl.DataFrame]] = None
    signals: Optional[pl.DataFrame] = None
    backtest_result: Optional[pl.DataFrame] = None

    @classmethod
    def from_dict(cls, data: dict) -> "BacktestSummary":
        """从Rust返回的字典创建BacktestSummary实例

        Args:
            data: Rust端返回的字典,包含performance/indicators/signals/backtest_result字段

        Returns:
            BacktestSummary实例
        """
        return cls(
            performance=data.get("performance"),
            indicators=data.get("indicators"),
            signals=data.get("signals"),
            backtest_result=data.get("backtest_result"),
        )

    def __repr__(self) -> str:
        """自定义字符串表示，避免打印大量DataFrame数据，并使用更简洁的表达式。"""

        perf_summary = f"{len(self.performance)} keys" if self.performance else "None"

        ind_summary = (
            f"[{', '.join(str(i.shape) for i in self.indicators)}]"
            if self.indicators
            else "None"
        )

        sig_summary = f"{self.signals.shape}" if self.signals is not None else "None"

        bt_summary = (
            f"{self.backtest_result.shape}"
            if self.backtest_result is not None
            else "None"
        )

        return (
            f"BacktestSummary("
            f"performance: {perf_summary}, "
            f"indicators shapes: {ind_summary}, "
            f"signals shape: {sig_summary}, "
            f"backtest_result shape: {bt_summary}"
            f")"
        )
