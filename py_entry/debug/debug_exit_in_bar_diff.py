"""
深度对比 exit_in_bar=True 下 Pyo3 和 BTP 官方 SL/TP 的差异

找出第一个分歧点
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

from typing import cast, Sequence
import dataclasses
import numpy as np
import pandas as pd
import pandas_ta as ta
from backtesting import Backtest
from backtesting.lib import crossover, TrailingStrategy

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)


# --- BTP 策略：官方 SL/TP ---
class BtpOfficialSLTP(TrailingStrategy):
    """官方 SL/TP 版本"""

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
    from py_entry.Test.backtest.strategies.reversal_extreme import config as cfg

    original_exit_in_bar = cfg.CONFIG.exit_in_bar
    cfg.CONFIG = dataclasses.replace(cfg.CONFIG, exit_in_bar=True)

    config = build_config_from_strategy("reversal_extreme")
    config.bars = 100
    config.seed = 42

    print("=== 运行配置 ===")
    print(f"bars: {config.bars}, seed: {config.seed}")

    # 1. 运行 Pyo3
    print("\n运行 Pyo3 (exit_in_bar=True)...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    pyo3_equity = pyo3_adapter.get_equity_curve()
    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 2. 运行 BTP
    print("运行 BTP (官方 SL/TP)...")
    ohlcv_df = generate_ohlcv_for_backtestingpy(config)

    bt = Backtest(ohlcv_df, BtpOfficialSLTP, cash=10000, commission=0)
    btp_stats = bt.run()
    btp_equity = btp_stats["_equity_curve"]["Equity"].values
    btp_trades = btp_stats["_trades"]

    # 恢复配置
    cfg.CONFIG = dataclasses.replace(cfg.CONFIG, exit_in_bar=original_exit_in_bar)

    print()
    print(f"Pyo3 最终净值: {pyo3_equity[-1]:.2f}")
    print(f"BTP 最终净值:  {btp_equity[-1]:.2f}")
    print()

    # 3. 找出第一个显著分歧点
    print("=== 寻找第一个分歧点 ===")

    min_len = min(len(pyo3_equity), len(btp_equity))
    for i in range(min_len):
        diff = abs(pyo3_equity[i] - btp_equity[i])
        if diff > 100:
            print(
                f"Bar {i}: Pyo3={pyo3_equity[i]:.2f}, BTP={btp_equity[i]:.2f}, 差异={diff:.2f}"
            )

            # 打印 Pyo3 在该 Bar 附近的状态
            print("\n=== Pyo3 Bar 附近状态 ===")
            context = pyo3_df.filter(
                (pyo3_df["bar_index"] >= max(0, i - 3))
                & (pyo3_df["bar_index"] <= i + 1)
            )
            cols = [
                "bar_index",
                "entry_long_price",
                "exit_long_price",
                "entry_short_price",
                "exit_short_price",
                "sl_pct_price_long",
                "sl_pct_price_short",
                "risk_in_bar_direction",
                "first_entry_side",
                "equity",
            ]
            print(context.select([c for c in cols if c in pyo3_df.columns]))

            # 打印 OHLC
            print("\n=== OHLC ===")
            for j in range(max(0, i - 3), min(i + 2, len(ohlcv_df))):
                row = ohlcv_df.iloc[j]
                print(
                    f"Bar {j}: O={row.Open:.4f}, H={row.High:.4f}, L={row.Low:.4f}, C={row.Close:.4f}"
                )

            # 打印 BTP 附近交易
            print("\n=== BTP 附近交易 ===")
            nearby = btp_trades[
                ((btp_trades["EntryBar"] >= i - 3) & (btp_trades["EntryBar"] <= i + 1))
                | ((btp_trades["ExitBar"] >= i - 3) & (btp_trades["ExitBar"] <= i + 1))
            ]
            if len(nearby) > 0:
                print(
                    nearby[
                        [
                            "EntryBar",
                            "ExitBar",
                            "Size",
                            "EntryPrice",
                            "ExitPrice",
                            "PnL",
                            "SL",
                            "TP",
                        ]
                    ].to_string()
                )
            else:
                print("无交易")

            break
    else:
        print("未找到显著分歧点 (差异 > 100)")

    # 4. 对比前几笔交易
    print("\n=== BTP 前 10 笔交易 ===")
    print(
        btp_trades[
            [
                "EntryBar",
                "ExitBar",
                "Size",
                "EntryPrice",
                "ExitPrice",
                "PnL",
                "SL",
                "TP",
            ]
        ]
        .head(10)
        .to_string()
    )

    # 5. 对比 Pyo3 前几个进/出场
    print("\n=== Pyo3 前 10 个进/出场事件 ===")
    events = pyo3_df.filter(
        (pyo3_df["first_entry_side"] != 0)
        | (pyo3_df["exit_long_price"].is_not_nan())
        | (pyo3_df["exit_short_price"].is_not_nan())
    ).head(20)
    print(
        events.select(
            [
                "bar_index",
                "first_entry_side",
                "entry_long_price",
                "exit_long_price",
                "entry_short_price",
                "exit_short_price",
                "sl_pct_price_long",
                "risk_in_bar_direction",
            ]
        )
    )


if __name__ == "__main__":
    main()
