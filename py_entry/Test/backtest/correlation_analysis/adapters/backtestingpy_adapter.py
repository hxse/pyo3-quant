"""
backtesting.py 回测引擎适配器

封装 backtesting.Backtest，提供统一接口用于相关性分析
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Type

from backtesting import Backtest, Strategy
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig


@dataclass
class BacktestingPyResult:
    """backtesting.py 回测结果"""

    stats: pd.Series
    equity: np.ndarray
    drawdown: np.ndarray


class BacktestingPyAdapter:
    """backtesting.py 回测引擎适配器"""

    def __init__(self, config: CommonConfig):
        """
        初始化适配器

        Args:
            config: 公共配置
        """
        self.config = config
        self.result: Optional[BacktestingPyResult] = None

    def run(
        self, data: pd.DataFrame, strategy_class: Type[Strategy]
    ) -> "BacktestingPyAdapter":
        """
        运行回测

        Args:
            data: OHLCV 数据
            strategy_class: 策略类

        Returns:
            self
        """
        # 这里故意直接使用 backtesting.py 的 Backtest，
        # 不走 shared builder，避免混淆两个引擎的适配边界。
        # 创建 Backtest 并运行
        bt = Backtest(
            data,
            strategy_class,
            cash=self.config.initial_capital,
            commission=self.config.commission / 2,
            exclusive_orders=True,  # 一次只能有一个仓位
        )

        # 抑制"未关闭仓位"警告（与 pyo3-quant 行为一致）
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Some trades remain open")
            stats = bt.run()

        # 提取净值曲线和回撤
        equity_curve = stats["_equity_curve"]
        equity = equity_curve["Equity"].values

        # 计算回撤百分比（与 pyo3-quant 一致，使用绝对值）
        peak = np.maximum.accumulate(equity)
        drawdown = np.abs((equity - peak) / peak)  # 取绝对值，使回撤为正数

        self.result = BacktestingPyResult(
            stats=stats,
            equity=equity,
            drawdown=drawdown,
        )

        return self

    def get_equity_curve(self) -> np.ndarray:
        """获取净值曲线"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return self.result.equity

    def get_drawdown_curve(self) -> np.ndarray:
        """获取回撤曲线"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return self.result.drawdown

    def get_total_return_pct(self) -> float:
        """获取总回报率"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return float(self.result.stats["Return [%]"])

    def get_trade_count(self) -> int:
        """获取交易次数"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return int(self.result.stats["# Trades"])

    def get_win_rate(self) -> float:
        """获取胜率（百分比格式）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return float(self.result.stats["Win Rate [%]"])
