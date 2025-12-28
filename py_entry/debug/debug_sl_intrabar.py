"""
验证 Backtesting.py 是否支持进场 Bar 内 SL 触发 (Intra-bar Exit)
"""

from backtesting import Backtest, Strategy
import pandas as pd
import numpy as np


def create_test_data():
    dates = pd.date_range("2024-01-01", periods=20, freq="15min")

    # 初始化
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

    # Bar 6: 进场 Bar - Low 触发 SL
    data.loc[data.index[6], "Open"] = 100.0  # 进场价
    data.loc[data.index[6], "High"] = 100.5
    data.loc[data.index[6], "Low"] = 97.0  # < SL=98，进场 Bar 内触发
    data.loc[data.index[6], "Close"] = 98.5

    # Bar 7
    data.loc[data.index[7], "Open"] = 98.5
    data.loc[data.index[7], "High"] = 99.0
    data.loc[data.index[7], "Low"] = 98.0
    data.loc[data.index[7], "Close"] = 98.5

    return data


class TestStrategy(Strategy):
    def init(self):
        pass

    def next(self):
        bar_idx = len(self.data) - 1

        if bar_idx == 5:
            entry = self.data.Close[-1]
            sl = entry * 0.98  # = 98
            print(f"Bar {bar_idx}: 下单 buy(sl={sl:.2f})")
            self.buy(sl=sl)


def main():
    data = create_test_data()

    print("=== 测试: 进场 Bar 内 SL 触发 ===")
    print()
    for i in [5, 6, 7]:
        row = data.iloc[i]
        print(
            f"Bar {i}: O={row['Open']:.1f}, H={row['High']:.1f}, L={row['Low']:.1f}, C={row['Close']:.1f}"
        )
    print()

    print("场景:")
    print("Bar 5: 信号, SL = 100 * 0.98 = 98")
    print("Bar 6: 进场 @ Open=100, Low=97 < SL=98 (进场 Bar 内触发)")
    print("问题: ExitBar 是 6 还是 7?")
    print()

    bt = Backtest(data, TestStrategy, cash=10000, commission=0)
    stats = bt.run()

    trades = stats["_trades"]
    if len(trades) > 0:
        t = trades.iloc[0]
        print(f"=== 结果 ===")
        print(f"EntryBar: {t['EntryBar']}")
        print(f"ExitBar: {t['ExitBar']}")
        print(f"EntryPrice: {t['EntryPrice']}")
        print(f"ExitPrice: {t['ExitPrice']}")
        print()

        if t["ExitBar"] == 6:
            print("结论: BTP 支持进场 Bar 内 SL 触发 (Intra-bar Exit)")
            print("这与 Pyo3 exit_in_bar=True 行为一致")
        elif t["ExitBar"] == 7:
            print("结论: BTP 不支持进场 Bar 内 SL 触发")
            print("SL 检查从进场 Bar 的下一根开始")


if __name__ == "__main__":
    main()
