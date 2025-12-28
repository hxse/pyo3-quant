"""
精确验证 Backtesting.py SL 成交价格
"""

from backtesting import Backtest, Strategy
import pandas as pd
import numpy as np


# 精确控制的测试数据
def create_test_data():
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


class TestSL(Strategy):
    def init(self):
        pass

    def next(self):
        if len(self.data) == 2 and not self.position:
            # Bar 1: 下单进场，设置 SL=98
            print(f"[Bar {len(self.data) - 1}] 下单: buy(sl=98)")
            self.buy(sl=98.0)


def main():
    data = create_test_data()

    print("=== 测试数据 ===")
    for i, row in data.iterrows():
        print(
            f"Bar {data.index.get_loc(i)}: O={row['Open']:.0f}, H={row['High']:.0f}, L={row['Low']:.0f}, C={row['Close']:.0f}"
        )
    print()

    print("=== 场景 ===")
    print("Bar 1: 下单 buy(sl=98)")
    print("Bar 2: 进场 @ Open=100, SL=98")
    print("Bar 3: Low=97 < SL=98 触发, Open=102")
    print()
    print("问题: 成交价是 SL(98) 还是 Open(102)?")
    print()

    bt = Backtest(data, TestSL, cash=10000, commission=0)
    stats = bt.run()

    trades = stats["_trades"]
    if len(trades) > 0:
        t = trades.iloc[0]
        print(f"=== 结果 ===")
        print(f"EntryBar: {t['EntryBar']}, ExitBar: {t['ExitBar']}")
        print(f"EntryPrice: {t['EntryPrice']}")
        print(f"ExitPrice: {t['ExitPrice']}")
        print(f"SL: {t['SL']}")
        print(f"PnL: {t['PnL']}")
        print()

        exit_price = t["ExitPrice"]
        if abs(exit_price - 98.0) < 0.01:
            print("结论: 成交价 = SL 价格 (98)")
        elif abs(exit_price - 102.0) < 0.01:
            print("结论: 成交价 = Open 价格 (102)")
        else:
            print(f"结论: 成交价 = {exit_price} (未知)")


if __name__ == "__main__":
    main()
