"""
严格验证 exit_in_bar=True 差异

1. 确保使用完全相同的数据
2. 确认 exit_in_bar 配置生效
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

from typing import cast, Sequence
import dataclasses
import numpy as np

# 在导入策略之前，先修改配置
from py_entry.Test.backtest.strategies.reversal_extreme import config as strategy_cfg

print("=== 修改前配置 ===")
print(f"exit_in_bar: {strategy_cfg.CONFIG.exit_in_bar}")

# 修改配置
strategy_cfg.CONFIG = dataclasses.replace(strategy_cfg.CONFIG, exit_in_bar=True)
print(f"修改后 exit_in_bar: {strategy_cfg.CONFIG.exit_in_bar}")
print()

# 现在导入其他模块
from py_entry.Test.backtest.strategies.reversal_extreme import get_config
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
    config.bars = 100
    config.seed = 42

    print("=== 运行配置 ===")
    print(f"bars: {config.bars}, seed: {config.seed}")

    # 1. 先生成 BTP 数据（使用 allow_gaps=False）
    print("\n生成共享 OHLCV 数据 (allow_gaps=False)...")
    ohlcv_df = generate_ohlcv_for_backtestingpy(config)

    # 2. 运行 Pyo3
    print("\n运行 Pyo3 (exit_in_bar=True)...")
    pyo3 = Pyo3Adapter(config)
    pyo3.run("reversal_extreme")

    # 验证 pyo3 的 exit_in_bar 配置
    # 获取实际使用的配置
    strategy = get_config()
    print(f"Pyo3 策略 exit_in_bar: {strategy.backtest_params.exit_in_bar}")

    assert pyo3.result is not None
    assert pyo3.runner is not None
    assert pyo3.runner.data_dict is not None

    pyo3_result = pyo3.result
    pyo3_runner = pyo3.runner

    assert pyo3_runner is not None
    assert pyo3_runner.data_dict is not None

    pyo3_df = pyo3_result.backtest_df.with_row_index("bar_index")
    pyo3_ohlc = pyo3_runner.data_dict.source[f"ohlcv_{config.timeframe}"]

    # 3. 运行 BTP
    print("运行 BTP (官方 SL/TP)...")
    bt = Backtest(ohlcv_df, BtpOfficialSLTP, cash=10000, commission=0)
    btp_stats = bt.run()
    btp_trades = btp_stats["_trades"]

    # 4. 验证数据一致性
    print("\n=== 验证数据一致性 ===")
    pyo3_open = pyo3_ohlc["open"].to_numpy()
    pyo3_low = pyo3_ohlc["low"].to_numpy()
    btp_open = ohlcv_df["Open"].values
    btp_low = ohlcv_df["Low"].values

    open_match = np.allclose(pyo3_open, btp_open, atol=0.0001)
    low_match = np.allclose(pyo3_low, btp_low, atol=0.0001)
    print(f"Open 一致: {open_match}")
    print(f"Low 一致: {low_match}")

    if not low_match:
        # 找出不一致的地方
        diff = np.abs(pyo3_low - btp_low)
        mismatch_idx = np.where(diff >= 0.0001)[0]
        print(f"Low 不一致的 Bar: {mismatch_idx[:5]}")
        for i in mismatch_idx[:3]:
            print(f"  Bar {i}: Pyo3 Low={pyo3_low[i]:.4f}, BTP Low={btp_low[i]:.4f}")

    # 5. 打印 Bar 60-62 详细信息
    print("\n=== Bar 60-62 详细 ===")
    for i in [60, 61, 62]:
        print(
            f"Bar {i}: Pyo3 L={pyo3_low[i]:.4f}, BTP L={btp_low[i]:.4f}, 一致: {abs(pyo3_low[i] - btp_low[i]) < 0.0001}"
        )

    # 6. 打印 Pyo3 Bar 60-62 的 SL 触发情况
    print("\n=== Pyo3 Bar 60-62 SL 触发情况 ===")
    subset = pyo3_df.filter((pyo3_df["bar_index"] >= 60) & (pyo3_df["bar_index"] <= 65))
    print(
        subset.select(
            [
                "bar_index",
                "entry_long_price",
                "exit_long_price",
                "sl_pct_price_long",
                "risk_in_bar_direction",
                "first_entry_side",
            ]
        )
    )

    print("\n=== BTP 第一笔交易 ===")
    if len(btp_trades) > 0:
        print(
            btp_trades[["EntryBar", "ExitBar", "Size", "EntryPrice", "ExitPrice", "SL"]]
            .head(1)
            .to_string()
        )

    print("\n=== 关键验证 ===")
    sl_price = 82.2279 * 0.98
    print(f"SL 价格: {sl_price:.4f}")
    print(f"Bar 61 Pyo3 Low: {pyo3_low[61]:.4f}")
    print(f"Bar 61 BTP Low:  {btp_low[61]:.4f}")
    print(f"Pyo3 触发 SL? {pyo3_low[61] <= sl_price}")
    print(f"BTP 触发 SL? {btp_low[61] <= sl_price}")


if __name__ == "__main__":
    main()
