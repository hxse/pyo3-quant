"""
逐笔对比 exit_in_bar=True 下 Pyo3 和 BTP 的交易
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

from typing import cast, Sequence
import dataclasses
import numpy as np

from py_entry.Test.backtest.strategies.reversal_extreme import (
    get_config,
    get_config as get_strategy,
)
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)

from backtesting import Backtest
from backtesting.lib import crossover, TrailingStrategy
import pandas as pd
import pandas_ta as ta


class BtpOfficialSLTP(TrailingStrategy):
    sl_pct = 0.02
    tp_atr = 4.0
    tsl_atr = 1.5
    bbands_period = 20
    bbands_std = 2.0
    atr_period = 14

    def init(self):
        super().init()
        self.set_atr_periods(self.atr_period)
        self.set_trailing_sl(n_atr=self.tsl_atr)
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)
        bbands = ta.bbands(
            close, length=self.bbands_period, std=self.bbands_std, talib=True
        )
        self.bbands_middle = self.I(
            lambda: bbands[f"BBM_{self.bbands_period}_{self.bbands_std}"].values
        )
        self.atr = self.I(ta.atr, high, low, close, length=self.atr_period, talib=True)

    def next(self):
        super().next()
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


def main():
    config = build_config_from_strategy("reversal_extreme")
    config.bars = 300  # 较少 bars 方便查看
    config.seed = 42

    print("=== 运行配置 ===")
    print(f"bars: {config.bars}, seed: {config.seed}")

    # 1. 运行 Pyo3
    print("\n运行 Pyo3 (exit_in_bar=True)...")
    pyo3 = Pyo3Adapter(config)
    pyo3.run("reversal_extreme")
    strategy = get_strategy("reversal_extreme")

    print(f"Pyo3 exit_in_bar: {strategy.backtest_params.exit_in_bar}")

    assert pyo3.result is not None
    assert pyo3.runner is not None

    pyo3_df = pyo3.result.backtest_df.with_row_index("bar_index")
    ohlcv_df = generate_ohlcv_for_backtestingpy(
        config
    )  # Reverted to original as the edit was syntactically incorrect
    bt = Backtest(ohlcv_df, BtpOfficialSLTP, cash=10000, commission=0)
    btp_stats = bt.run()
    btp_trades = btp_stats["_trades"]

    print(f"\nPyo3 最终净值: {pyo3.get_equity_curve()[-1]:.2f}")
    print(f"BTP 最终净值: {btp_stats['_equity_curve']['Equity'].values[-1]:.2f}")

    # 3. 对比前 10 笔交易
    print("\n=== BTP 前 10 笔交易 ===")
    print(
        btp_trades[
            ["EntryBar", "ExitBar", "Size", "EntryPrice", "ExitPrice", "PnL", "SL"]
        ]
        .head(10)
        .to_string()
    )

    # 4. Pyo3 进出场事件
    print("\n=== Pyo3 前 15 个进出场 ===")
    pyo3_events = pyo3_df.filter(
        (pyo3_df["first_entry_side"] != 0)
        | (pyo3_df["exit_long_price"].is_not_nan())
        | (pyo3_df["exit_short_price"].is_not_nan())
    ).head(15)
    cols = [
        "bar_index",
        "first_entry_side",
        "entry_long_price",
        "exit_long_price",
        "entry_short_price",
        "exit_short_price",
        "risk_in_bar_direction",
    ]
    print(pyo3_events.select([c for c in cols if c in pyo3_df.columns]))

    # 5. 构造 Pyo3 交易记录
    print("\n=== 构造 Pyo3 交易记录 ===")
    pyo3_trades = []
    current_trade = None

    for row in pyo3_df.iter_rows(named=True):
        bar = row["bar_index"]

        # 检查进场
        if row["first_entry_side"] == 1:  # 多头进场
            current_trade = {
                "EntryBar": bar,
                "Side": "Long",
                "EntryPrice": row["entry_long_price"],
            }
        elif row["first_entry_side"] == -1:  # 空头进场
            current_trade = {
                "EntryBar": bar,
                "Side": "Short",
                "EntryPrice": row["entry_short_price"],
            }

        # 检查离场
        if current_trade:
            exit_price = None
            if (
                current_trade["Side"] == "Long"
                and row["exit_long_price"] is not None
                and not np.isnan(row["exit_long_price"])
            ):
                exit_price = row["exit_long_price"]
            elif (
                current_trade["Side"] == "Short"
                and row["exit_short_price"] is not None
                and not np.isnan(row["exit_short_price"])
            ):
                exit_price = row["exit_short_price"]

            if exit_price is not None:
                current_trade["ExitBar"] = bar
                current_trade["ExitPrice"] = exit_price
                pyo3_trades.append(current_trade)
                current_trade = None

    print(f"Pyo3 交易数: {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")

    print("\nPyo3 前 10 笔交易:")
    for i, t in enumerate(pyo3_trades[:10]):
        print(
            f"  {i}: Entry={t['EntryBar']}, Exit={t['ExitBar']}, Side={t['Side']}, EntryP={t['EntryPrice']:.2f}, ExitP={t['ExitPrice']:.2f}"
        )

    # 6. 找第一个分歧
    print("\n=== 寻找第一个分歧 ===")
    for i in range(min(len(pyo3_trades), len(btp_trades))):
        pt = pyo3_trades[i]
        bt_row = btp_trades.iloc[i]

        if pt["EntryBar"] != bt_row["EntryBar"] or pt["ExitBar"] != bt_row["ExitBar"]:
            print(f"交易 #{i} 分歧:")
            print(
                f"  Pyo3: Entry={pt['EntryBar']}, Exit={pt['ExitBar']}, Side={pt['Side']}"
            )
            print(
                f"  BTP:  Entry={bt_row['EntryBar']}, Exit={bt_row['ExitBar']}, Size={bt_row['Size']}"
            )
            break
    else:
        print(f"前 {min(len(pyo3_trades), len(btp_trades))} 笔交易完全匹配！")


if __name__ == "__main__":
    main()
