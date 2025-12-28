"""
深度分析手动 SL/TP vs 官方 SL/TP 的行为差异

直接在 backtesting.py 内部对比两种实现
"""

from backtesting import Backtest, Strategy
from backtesting.lib import crossover, TrailingStrategy
import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import cast, Sequence


# 生成无跳空的测试数据
def generate_no_gap_data(num_bars=500, seed=42):
    np.random.seed(seed)

    initial_price = 100.0
    volatility = 0.02

    # 生成收益率
    returns = np.random.normal(0, volatility, num_bars)
    price_multipliers = 1.0 + returns
    close_prices = initial_price * np.cumprod(price_multipliers)

    # 无跳空：Open = 前一个 Close
    prev_close = np.concatenate([[initial_price], close_prices[:-1]])
    open_prices = prev_close  # 关键：无跳空

    # High/Low
    range_factors = np.abs(np.random.normal(0, volatility / 3, num_bars))
    max_oc = np.maximum(open_prices, close_prices)
    min_oc = np.minimum(open_prices, close_prices)
    high_prices = max_oc + range_factors * max_oc
    low_prices = min_oc - range_factors * min_oc

    volumes = np.abs(np.random.normal(1000000, 200000, num_bars))

    # 创建 DataFrame
    dates = pd.date_range("2024-01-01", periods=num_bars, freq="15min")
    df = pd.DataFrame(
        {
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": volumes,
        },
        index=dates,
    )

    return df


# 策略 1：官方 SL/TP（使用 buy(sl=..., tp=...)）
class OfficialSLTP(Strategy):
    sl_pct = 0.02
    tp_atr = 4.0

    def init(self):
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)

        bbands = ta.bbands(close, length=20, std=2.0, talib=True)
        self.bbands_middle = self.I(lambda: bbands["BBM_20_2.0"].values)
        self.atr = self.I(ta.atr, high, low, close, length=14, talib=True)

    def next(self):
        atr = self.atr[-1]

        if crossover(
            cast(Sequence, self.data.Close), cast(Sequence, self.bbands_middle)
        ):
            entry = self.data.Close[-1]
            self.buy(sl=entry * (1 - self.sl_pct), tp=entry + atr * self.tp_atr)

        elif crossover(
            cast(Sequence, self.bbands_middle), cast(Sequence, self.data.Close)
        ):
            entry = self.data.Close[-1]
            self.sell(sl=entry * (1 + self.sl_pct), tp=entry - atr * self.tp_atr)


# 策略 2：手动 SL/TP（使用 position.close()）
class ManualSLTP(Strategy):
    sl_pct = 0.02
    tp_atr = 4.0

    def init(self):
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)

        bbands = ta.bbands(close, length=20, std=2.0, talib=True)
        self.bbands_middle = self.I(lambda: bbands["BBM_20_2.0"].values)
        self.atr = self.I(ta.atr, high, low, close, length=14, talib=True)

        self.sl_price = None
        self.tp_price = None
        self.last_trade = None

    def next(self):
        atr = self.atr[-1]

        # 手动 SL/TP 检查
        if self.position:
            if self.trades[-1] != self.last_trade:
                entry_price = self.trades[-1].entry_price
                if self.position.is_long:
                    self.sl_price = entry_price * (1 - self.sl_pct)
                    self.tp_price = entry_price + atr * self.tp_atr
                else:
                    self.sl_price = entry_price * (1 + self.sl_pct)
                    self.tp_price = entry_price - atr * self.tp_atr
                self.last_trade = self.trades[-1]

            # 手动检查并离场
            if self.position.is_long:
                if self.data.Low[-1] <= self.sl_price:
                    self.position.close()
                    return
                if self.data.High[-1] >= self.tp_price:
                    self.position.close()
                    return
            else:
                if self.data.High[-1] >= self.sl_price:
                    self.position.close()
                    return
                if self.data.Low[-1] <= self.tp_price:
                    self.position.close()
                    return
        else:
            self.sl_price = None
            self.tp_price = None
            self.last_trade = None

        # 进场信号（不带 SL/TP）
        # 进场信号（不带 SL/TP）
        if crossover(
            cast(Sequence, self.data.Close), cast(Sequence, self.bbands_middle)
        ):
            self.buy()
        elif crossover(
            cast(Sequence, self.bbands_middle), cast(Sequence, self.data.Close)
        ):
            self.sell()


def analyze_trades(trades_df, name):
    """分析交易详情"""
    print(f"\n{'=' * 60}")
    print(f"{name} 交易分析")
    print(f"{'=' * 60}")

    print(f"总交易数: {len(trades_df)}")

    # 统计 SL/TP 触发的交易
    sl_trades = trades_df[trades_df["SL"].notna() & (trades_df["SL"] != 0)]
    tp_trades = trades_df[trades_df["TP"].notna() & (trades_df["TP"] != 0)]

    print(f"SL 触发次数: {len(sl_trades)}")
    print(f"TP 触发次数: {len(tp_trades)}")

    # 统计进场-离场同 Bar 的交易
    same_bar = trades_df[trades_df["EntryBar"] == trades_df["ExitBar"]]
    print(f"进场-离场同 Bar 次数: {len(same_bar)}")

    # 显示前 10 笔交易
    print(f"\n前 10 笔交易:")
    cols = ["EntryBar", "ExitBar", "Size", "EntryPrice", "ExitPrice", "PnL", "SL", "TP"]
    print(trades_df[cols].head(10).to_string())

    return trades_df


def main():
    # 生成数据
    data = generate_no_gap_data(num_bars=500, seed=42)
    print(f"数据生成完成: {len(data)} bars")
    print(f"价格范围: {data['Close'].min():.2f} - {data['Close'].max():.2f}")

    # 运行官方 SL/TP 策略
    bt_official = Backtest(data, OfficialSLTP, cash=10000, commission=0.001)
    stats_official = bt_official.run()

    # 运行手动 SL/TP 策略
    bt_manual = Backtest(data, ManualSLTP, cash=10000, commission=0.001)
    stats_manual = bt_manual.run()

    # 分析结果
    print("\n" + "=" * 60)
    print("结果对比")
    print("=" * 60)
    print(f"{'指标':<20} {'官方 SL/TP':<15} {'手动 SL/TP':<15}")
    print(f"{'-' * 50}")
    print(
        f"{'最终净值':<20} {stats_official['Equity Final [$]']:<15.2f} {stats_manual['Equity Final [$]']:<15.2f}"
    )
    print(
        f"{'总回报率':<20} {stats_official['Return [%]']:<15.2f} {stats_manual['Return [%]']:<15.2f}"
    )
    print(
        f"{'最大回撤':<20} {stats_official['Max. Drawdown [%]']:<15.2f} {stats_manual['Max. Drawdown [%]']:<15.2f}"
    )
    print(
        f"{'交易次数':<20} {stats_official['# Trades']:<15} {stats_manual['# Trades']:<15}"
    )
    print(
        f"{'胜率':<20} {stats_official['Win Rate [%]']:<15.2f} {stats_manual['Win Rate [%]']:<15.2f}"
    )

    # 分析交易详情
    trades_official = analyze_trades(stats_official["_trades"], "官方 SL/TP")
    trades_manual = analyze_trades(stats_manual["_trades"], "手动 SL/TP")

    # 对比关键差异
    print("\n" + "=" * 60)
    print("关键差异分析")
    print("=" * 60)

    # 找出第一个分歧点
    min_len = min(len(trades_official), len(trades_manual))
    for i in range(min_len):
        t_off = trades_official.iloc[i]
        t_man = trades_manual.iloc[i]

        if (
            t_off["EntryBar"] != t_man["EntryBar"]
            or t_off["ExitBar"] != t_man["ExitBar"]
        ):
            print(f"\n首个分歧点在第 {i + 1} 笔交易:")
            print(f"\n官方 SL/TP:")
            print(f"  EntryBar: {t_off['EntryBar']}, ExitBar: {t_off['ExitBar']}")
            print(
                f"  EntryPrice: {t_off['EntryPrice']:.4f}, ExitPrice: {t_off['ExitPrice']:.4f}"
            )
            print(f"  SL: {t_off['SL']}, TP: {t_off['TP']}")
            print(f"  PnL: {t_off['PnL']:.4f}")

            print(f"\n手动 SL/TP:")
            print(f"  EntryBar: {t_man['EntryBar']}, ExitBar: {t_man['ExitBar']}")
            print(
                f"  EntryPrice: {t_man['EntryPrice']:.4f}, ExitPrice: {t_man['ExitPrice']:.4f}"
            )
            print(f"  SL: {t_man['SL']}, TP: {t_man['TP']}")
            print(f"  PnL: {t_man['PnL']:.4f}")

            # 打印该 Bar 的 OHLC 数据
            entry_bar = int(t_off["EntryBar"])
            exit_bar_off = int(t_off["ExitBar"])
            exit_bar_man = int(t_man["ExitBar"])

            print(f"\n相关 Bar 的 OHLC 数据:")
            for bar_idx in range(
                max(0, entry_bar - 1),
                min(len(data), max(exit_bar_off, exit_bar_man) + 2),
            ):
                row = data.iloc[bar_idx]
                print(
                    f"  Bar {bar_idx}: O={row['Open']:.4f}, H={row['High']:.4f}, L={row['Low']:.4f}, C={row['Close']:.4f}"
                )

            break
    else:
        print("前 {} 笔交易完全一致！".format(min_len))


if __name__ == "__main__":
    main()
