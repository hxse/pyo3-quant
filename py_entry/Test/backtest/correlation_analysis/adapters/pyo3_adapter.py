"""
pyo3-quant 回测引擎适配器

封装 BacktestRunner，提供统一接口用于相关性分析
"""

import polars as pl
import numpy as np
from dataclasses import dataclass
from typing import Optional

from py_entry.runner import Backtest
from py_entry.Test.backtest.strategies import get_strategy
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig


@dataclass
class Pyo3BacktestResult:
    """pyo3-quant 回测结果"""

    backtest_df: pl.DataFrame
    equity: np.ndarray
    balance: np.ndarray
    drawdown: np.ndarray


class Pyo3Adapter:
    """pyo3-quant 回测引擎适配器"""

    def __init__(self, config: CommonConfig):
        self.config = config
        self.runner: Optional[Backtest] = None
        self.result: Optional[Pyo3BacktestResult] = None

    def run(self, strategy_name: str) -> "Pyo3Adapter":
        """
        运行回测

        Args:
            strategy_name: 策略注册表中的策略名称

        Returns:
            self（链式调用）
        """
        # 获取策略配置
        strategy = get_strategy(strategy_name)

        # 动态覆盖数据配置（根据 CommonConfig）
        strategy.data_config.num_bars = self.config.bars
        strategy.data_config.fixed_seed = self.config.seed
        strategy.data_config.start_time = self.config.start_time
        strategy.data_config.timeframes = [self.config.timeframe]
        strategy.data_config.base_data_key = f"ohlcv_{self.config.timeframe}"

        # 覆盖回测参数
        strategy.backtest_params.initial_capital = self.config.initial_capital
        strategy.backtest_params.fee_pct = self.config.commission

        # 创建 Backtest 并执行
        self.runner = Backtest(
            data_source=strategy.data_config,
            indicators=strategy.indicators_params,
            signal=strategy.signal_params,
            backtest=strategy.backtest_params,
            signal_template=strategy.signal_template,
            engine_settings=strategy.engine_settings,
            performance=strategy.performance_params,
        )
        result = self.runner.run()

        # 提取结果
        assert result.summary is not None, "回测结果为空"
        summary = result.summary
        backtest_df = summary.backtest_result

        assert backtest_df is not None, "回测结果 DataFrame 为空"

        self.result = Pyo3BacktestResult(
            backtest_df=backtest_df,
            equity=backtest_df["equity"].to_numpy(),
            balance=backtest_df["balance"].to_numpy(),
            drawdown=backtest_df["current_drawdown"].to_numpy(),
        )

        return self

    def get_equity_curve(self) -> np.ndarray:
        """获取净值曲线（equity）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return self.result.equity

    def get_balance_curve(self) -> np.ndarray:
        """获取余额曲线（balance）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return self.result.balance

    def get_drawdown_curve(self) -> np.ndarray:
        """获取回撤曲线"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        return self.result.drawdown

    def get_total_return_pct(self) -> float:
        """获取总回报率（百分比格式）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")
        # 从最后一行获取 total_return_pct（小数格式），转换为百分比
        return float(self.result.backtest_df["total_return_pct"][-1]) * 100

    def get_trade_count(self) -> int:
        """获取交易次数（基于 exit 信号，分别统计 long 和 short）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")

        df = self.result.backtest_df
        # 分别统计 exit_long 和 exit_short（反手时可能同时触发）
        long_exits = df.filter(pl.col("exit_long_price").is_not_nan()).height
        short_exits = df.filter(pl.col("exit_short_price").is_not_nan()).height
        return long_exits + short_exits

    def get_win_rate(self) -> float:
        """获取胜率（基于 exit 时的 pnl）"""
        if self.result is None:
            raise RuntimeError("请先调用 run() 方法")

        df = self.result.backtest_df
        exit_mask = (
            pl.col("exit_long_price").is_not_nan()
            | pl.col("exit_short_price").is_not_nan()
        )
        exit_trades = df.filter(exit_mask)

        total_trades = exit_trades.height
        if total_trades == 0:
            return 0.0

        # 统计盈利交易 (pnl > 0)
        win_count = exit_trades.filter(pl.col("trade_pnl_pct") > 0.0).height
        return (win_count / total_trades) * 100
