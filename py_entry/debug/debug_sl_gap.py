"""
验证当 Open < SL 时（跳空低开），两者的成交价差异
"""

from backtesting import Backtest, Strategy
import pandas as pd


# 测试数据：跳空低开 Open < SL
def create_gap_data():
    dates = pd.date_range("2024-01-01", periods=5, freq="15min")

    data = pd.DataFrame(
        {
            "Open": [
                100.0,
                100.0,
                100.0,
                95.0,
                96.0,
            ],  # Bar 3 Open=95 < SL=98 (跳空低开)
            "High": [101.0, 101.0, 101.0, 96.0, 97.0],
            "Low": [99.0, 99.0, 99.0, 94.0, 95.0],  # Bar 3 Low=94 < SL=98 触发
            "Close": [100.0, 100.0, 100.0, 95.5, 96.0],
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
            self.buy(sl=98.0)


def main():
    data = create_gap_data()

    print("=== 跳空低开场景 ===")
    print("Bar 2: 进场 @ Open=100, SL=98")
    print("Bar 3: 跳空低开 Open=95 < SL=98, Low=94")
    print()

    bt = Backtest(data, TestSL, cash=10000, commission=0)
    stats = bt.run()

    trades = stats["_trades"]
    if len(trades) > 0:
        t = trades.iloc[0]
        exit_price = t["ExitPrice"]
        print(f"ExitPrice: {exit_price}")
        print()

        if abs(exit_price - 95.0) < 0.01:
            print("结论: Backtesting.py 成交价 = min(Open, SL) = 95 (模拟跳空滑点)")
        elif abs(exit_price - 98.0) < 0.01:
            print("结论: Backtesting.py 成交价 = SL = 98")
        else:
            print(f"结论: 成交价 = {exit_price}")

        print()
        print("Pyo3 exit_in_bar=True 时，成交价始终 = SL = 98")
        print("差异: Pyo3 会产生更好的成交价，导致净值偏离")


if __name__ == "__main__":
    main()
