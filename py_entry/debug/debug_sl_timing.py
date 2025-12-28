"""
精确对比 Pyo3 和 Backtesting.py 的 SL 时序

关键问题：进场后，SL 触发检查是在哪根 Bar？
"""

from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np


# 创建一个精确控制的场景
def create_test_data():
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=20, freq="15min")

    # 无跳空数据：Open[i] = Close[i-1]
    close = [100.0]
    for i in range(1, 20):
        change = np.random.uniform(-0.02, 0.02)
        close.append(close[-1] * (1 + change))

    open_prices = [100.0] + close[:-1]  # Open = prev Close (无跳空)

    data = pd.DataFrame(
        {
            "Open": open_prices,
            "High": [max(o, c) * 1.005 for o, c in zip(open_prices, close)],
            "Low": [min(o, c) * 0.995 for o, c in zip(open_prices, close)],
            "Close": close,
            "Volume": [1000] * 20,
        },
        index=dates,
    )

    # 在 Bar 5 制造一个明确的信号和 SL 触发场景
    # Bar 5: 信号 Bar
    # Bar 6: 进场 Bar
    # Bar 7: SL 触发 Bar

    # 重新设置关键 Bar 的价格，制造下跌触发 SL
    data.loc[data.index[5], "Close"] = 100.0  # 信号 Bar Close
    data.loc[data.index[6], "Open"] = 100.0  # 进场 Bar Open (= prev Close)
    data.loc[data.index[6], "High"] = 100.5
    data.loc[data.index[6], "Low"] = 99.0  # 低点，但不触发 SL (SL=98)
    data.loc[data.index[6], "Close"] = 99.5
    data.loc[data.index[7], "Open"] = 99.5  # = prev Close (无跳空)
    data.loc[data.index[7], "High"] = 99.8
    data.loc[data.index[7], "Low"] = 97.0  # 低点触发 SL (SL=98)
    data.loc[data.index[7], "Close"] = 97.5

    return data


class TestStrategy(Strategy):
    def init(self):
        # 简单的 SMA 交叉进场
        self.sma = self.I(lambda x: pd.Series(x).rolling(3).mean(), self.data.Close)

    def next(self):
        bar_idx = len(self.data) - 1

        # Bar 5: 强制产生进场信号
        if bar_idx == 5:
            entry = self.data.Close[-1]
            sl = entry * 0.98  # 2% SL
            print(f"Bar {bar_idx}: 下单 buy(sl={sl:.2f}), entry_basis={entry:.2f}")
            self.buy(sl=sl)


def main():
    data = create_test_data()

    print("=== 测试数据 (关键 Bar) ===")
    for i in [5, 6, 7, 8]:
        row = data.iloc[i]
        print(
            f"Bar {i}: O={row['Open']:.2f}, H={row['High']:.2f}, L={row['Low']:.2f}, C={row['Close']:.2f}"
        )
    print()

    print("=== 预期行为 ===")
    print("Bar 5: 信号产生, SL = 100 * 0.98 = 98")
    print("Bar 6: 进场 @ Open=100, Low=99 > SL=98 (不触发)")
    print("Bar 7: Low=97 < SL=98 (触发)")
    print()

    bt = Backtest(data, TestStrategy, cash=10000, commission=0)
    stats = bt.run()

    trades = stats["_trades"]
    if len(trades) > 0:
        t = trades.iloc[0]
        print(f"=== 交易结果 ===")
        print(f"EntryBar: {t['EntryBar']}")
        print(f"ExitBar: {t['ExitBar']}")
        print(f"EntryPrice: {t['EntryPrice']}")
        print(f"ExitPrice: {t['ExitPrice']}")
        print(f"SL: {t['SL']}")
        print()

        if t["ExitBar"] == 6:
            print("结论: BTP 在进场 Bar 内就检查 SL (Intra-bar)")
        elif t["ExitBar"] == 7:
            print("结论: BTP 在进场 Bar 之后检查 SL")

        print()
        print("Pyo3 exit_in_bar=True: 也应该在进场 Bar 内检查")
        print("需要确认两者的 ExitBar 是否一致")


if __name__ == "__main__":
    main()
