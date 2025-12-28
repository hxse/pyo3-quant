"""
双均线交叉策略 - backtesting.py 实现

策略逻辑:
- 快线: SMA(5)
- 慢线: SMA(10)
- 进场: 金叉做多，死叉做空
- 离场: 反向交叉
"""

from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd
import pandas_ta as ta

from .config import CONFIG as C


class SmaCrossoverBtp(Strategy):
    """backtesting.py 版本的双均线交叉策略"""

    def init(self):
        # 使用共享配置计算指标（使用 pandas-ta talib=True 模式）
        close = pd.Series(self.data.Close)
        self.sma_fast = self.I(ta.sma, close, length=C.sma_fast_period, talib=True)
        self.sma_slow = self.I(ta.sma, close, length=C.sma_slow_period, talib=True)

    def next(self):
        # 金叉：快线上穿慢线 -> 做多
        if crossover(self.sma_fast, self.sma_slow):  # type: ignore
            self.position.close()
            self.buy()

        # 死叉：快线下穿慢线 -> 做空
        elif crossover(self.sma_slow, self.sma_fast):  # type: ignore
            self.position.close()
            self.sell()
