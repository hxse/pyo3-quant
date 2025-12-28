"""
对比 TP 触发逻辑

BTP: TP 是 limit order，使用 low <= limit (做多买入) 或 high >= limit (做空卖出) 触发
Pyo3: TP 触发检测用什么价格？
"""

from backtesting import Backtest, Strategy
import pandas as pd


def create_test_data():
    dates = pd.date_range("2024-01-01", periods=20, freq="15min")

    data = pd.DataFrame(
        {
            "Open": [100.0] * 20,
            "High": [101.0] * 20,
            "Low": [99.0] * 20,
            "Close": [100.0] * 20,
            "Volume": [1000] * 20,
        },
        index=dates,
    )

    # Bar 5: 信号 Bar
    data.loc[data.index[5], "Close"] = 100.0

    # Bar 6: 进场 Bar - High 触发 TP
    data.loc[data.index[6], "Open"] = 100.0  # 进场价
    data.loc[data.index[6], "High"] = 105.0  # > TP=104 (4% TP)
    data.loc[data.index[6], "Low"] = 99.5
    data.loc[data.index[6], "Close"] = 104.5

    return data


class TestTPStrategy(Strategy):
    def init(self):
        pass

    def next(self):
        bar_idx = len(self.data) - 1

        if bar_idx == 5:
            entry = self.data.Close[-1]
            tp = entry * 1.04  # = 104
            print(f"Bar {bar_idx}: 下单 buy(tp={tp:.2f})")
            self.buy(tp=tp)


def main():
    data = create_test_data()

    print("=== TP 触发测试 ===")
    print()
    for i in [5, 6]:
        row = data.iloc[i]
        print(
            f"Bar {i}: O={row['Open']:.1f}, H={row['High']:.1f}, L={row['Low']:.1f}, C={row['Close']:.1f}"
        )
    print()

    print("场景:")
    print("Bar 5: 信号, TP = 100 * 1.04 = 104")
    print("Bar 6: 进场 @ Open=100, High=105 > TP=104")
    print()

    bt = Backtest(data, TestTPStrategy, cash=10000, commission=0)
    stats = bt.run()

    trades = stats["_trades"]
    if len(trades) > 0:
        t = trades.iloc[0]
        print(f"=== 结果 ===")
        print(f"EntryBar: {t['EntryBar']}, ExitBar: {t['ExitBar']}")
        print(f"EntryPrice: {t['EntryPrice']}")
        print(f"ExitPrice: {t['ExitPrice']}")
        print(f"TP: {t['TP']}")
        print()

        if t["ExitPrice"] == 104.0:
            print("结论: BTP TP 成交价 = TP 价格")
        elif t["ExitPrice"] == 105.0:
            print("结论: BTP TP 成交价 = High")
        else:
            print(f"结论: BTP TP 成交价 = {t['ExitPrice']}")


if __name__ == "__main__":
    main()
