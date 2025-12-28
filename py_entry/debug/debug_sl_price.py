"""
验证 Backtesting.py 的 SL 成交价格逻辑

关键发现：Backtesting.py 使用 max(Open, SL) 作为成交价（多头）
"""

from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np


# 构造一个精确控制的场景
def create_test_data():
    """创建测试数据：
    Bar 0: 进场信号
    Bar 1: 进场成交 (Open=100)
    Bar 2: SL 触发场景 - Low < SL < Open
    """
    dates = pd.date_range("2024-01-01", periods=5, freq="15min")

    data = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 102.0, 101.0],  # Bar 3 Open=102 > SL=98
            "High": [101.0, 101.0, 101.0, 103.0, 102.0],
            "Low": [99.0, 99.0, 99.0, 97.0, 100.0],  # Bar 3 Low=97 < SL=98 触发
            "Close": [100.0, 100.0, 100.0, 101.0, 101.0],
            "Volume": [1000] * 5,
        },
        index=dates,
    )

    return data


class TestSLPrice(Strategy):
    def init(self):
        self.entry_bar = None

    def next(self):
        if len(self.data) == 2 and not self.position:
            # Bar 1: 下单进场，设置 SL=98 (2% 止损)
            self.buy(sl=98.0)
            self.entry_bar = len(self.data)
            print(f"[Bar {len(self.data) - 1}] 下单进场: SL=98.0")


def main():
    data = create_test_data()

    print("=== 测试数据 ===")
    print(data.to_string())
    print()

    print("=== 场景说明 ===")
    print("Bar 1: 下单进场，SL=98")
    print("Bar 2: 进场成交 @ Open=100")
    print("Bar 3: Low=97 < SL=98 (触发), 但 Open=102 > SL=98")
    print("问题: 成交价是 98 还是 102?")
    print()

    bt = Backtest(data, TestSLPrice, cash=10000, commission=0)
    stats = bt.run()

    print("=== 交易记录 ===")
    trades = stats["_trades"]
    print(
        trades[
            ["EntryBar", "ExitBar", "EntryPrice", "ExitPrice", "SL", "PnL"]
        ].to_string()
    )

    if len(trades) > 0:
        exit_price = trades.iloc[0]["ExitPrice"]
        print(f"\n=== 关键发现 ===")
        print(f"SL 价格:    98.0")
        print(f"触发 Bar Open: 102.0")
        print(f"实际成交价:  {exit_price}")

        if exit_price == 98.0:
            print("\n结论: Backtesting.py 使用 SL 价格成交")
        elif exit_price == 102.0:
            print("\n结论: Backtesting.py 使用 max(Open, SL) = Open 成交")
        else:
            print(f"\n意外结果: 成交价既不是 SL 也不是 Open")


if __name__ == "__main__":
    main()
