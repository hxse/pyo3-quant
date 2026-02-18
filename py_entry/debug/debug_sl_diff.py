"""
深入对比 Pyo3 和 BTP 的 SL 差异来源

关键问题: 在交易 #1 中
- Pyo3 SL 出场价: 80.9290
- BTP  SL 出场价: 80.7357

差异: 0.1934 (BTP 更低)

需要验证:
1. 两者使用的 signal_close 是否相同
2. 两者使用的 ATR 是否相同
3. TSL 更新逻辑是否导致了 SL 变化
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import pandas as pd
import pandas_ta as ta


from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.strategies.reversal_extreme.config import CONFIG as C

from backtesting import Backtest
from backtesting.lib import crossover, TrailingStrategy
from typing import cast, Sequence


# 全局日志收集
ENTRY_LOGS = []


class DebugReversalExtreme(TrailingStrategy):
    """带详细日志的 BTP 策略"""

    def init(self):
        super().init()
        self.set_atr_periods(C.atr_period)
        self.set_trailing_sl(n_atr=C.tsl_atr)

        # BBands (直接调用 pandas_ta)
        self.bbands_upper, self.bbands_middle, self.bbands_lower = self.I(
            lambda: (
                ta.bbands(
                    pd.Series(self.data.Close),
                    length=C.bbands_period,
                    std=C.bbands_std,
                    talib=True,
                )
                .iloc[:, [2, 1, 0]]
                .values.T
            )
        )

        # ATR (直接调用 pandas_ta)
        self.atr = self.I(
            lambda: (
                ta.atr(
                    pd.Series(self.data.High),
                    pd.Series(self.data.Low),
                    pd.Series(self.data.Close),
                    length=C.atr_period,
                    talib=True,
                ).values
            )
        )

        self.extremum = None

    def next(self):
        super().next()

        bar_idx = len(self.data) - 1
        close = self.data.Close[-1]
        atr = self.atr[-1]

        # 信号检测
        entry_short = crossover(
            cast(Sequence, self.bbands_middle), cast(Sequence, self.data.Close)
        )

        if entry_short and not self.position.is_short:
            # 计算 SL
            sl_fixed = close * (1 + C.sl_pct)
            tsl_init = close + atr * C.tsl_atr if C.tsl_atr > 0 else float("inf")
            initial_sl = min(sl_fixed, tsl_init)
            tp_fixed = close - atr * C.tp_atr

            ENTRY_LOGS.append(
                {
                    "bar": bar_idx,
                    "close": close,
                    "atr": atr,
                    "sl_fixed": sl_fixed,
                    "tsl_init": tsl_init,
                    "initial_sl": initial_sl,
                }
            )

            if self.position.is_long:
                self.position.close()

            self.sell(sl=initial_sl, tp=tp_fixed, size=0.99)
            self.extremum = None


def main():
    global ENTRY_LOGS
    ENTRY_LOGS = []  # 重置
    config = build_config_from_strategy("reversal_extreme", bars=100, seed=42)

    # 运行 Pyo3 获取数据
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None
    assert pyo3_adapter.runner.data_dict is not None

    # 获取 OHLCV 数据
    base_key = f"ohlcv_{config.timeframe}"
    pyo3_pl_df = pyo3_adapter.runner.data_dict.source[base_key]
    ohlcv_df = pyo3_pl_df.to_pandas()

    ohlcv_df = ohlcv_df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "time": "Time",
        }
    )
    ohlcv_df["Time"] = pd.to_datetime(ohlcv_df["Time"], unit="ms")
    ohlcv_df = ohlcv_df.set_index("Time")

    # 运行 BTP
    print("运行 BTP...")
    bt = Backtest(ohlcv_df, DebugReversalExtreme, cash=10000, commission=0)
    stats = bt.run()

    # 打印 BTP 的进场日志
    print("\n=== BTP 进场日志 (空头) ===")
    for log in ENTRY_LOGS:
        print(f"Bar {log['bar']}: close={log['close']:.4f}, atr={log['atr']:.4f}")
        print(
            f"  sl_fixed = {log['close']:.4f} * (1 + {C.sl_pct}) = {log['sl_fixed']:.4f}"
        )
        print(
            f"  tsl_init = {log['close']:.4f} + {log['atr']:.4f} * {C.tsl_atr} = {log['tsl_init']:.4f}"
        )
        print(
            f"  initial_sl = min({log['sl_fixed']:.4f}, {log['tsl_init']:.4f}) = {log['initial_sl']:.4f}"
        )
        print()

    # 打印 BTP 交易
    print("=== BTP 交易 ===")
    trades = stats["_trades"]
    short_trades = trades[trades["Size"] < 0]
    print(
        short_trades[["EntryBar", "ExitBar", "EntryPrice", "ExitPrice", "SL"]]
        .head(5)
        .to_string()
    )

    # 打印 Pyo3 Bar 63 的数据
    print("\n=== Pyo3 对比 ===")
    pyo3_df = pyo3_adapter.result.backtest_df
    print(f"Bar 62 signal_close: {ohlcv_df['Close'].iloc[62]:.4f}")
    print(f"Pyo3 ATR at 62: {pyo3_df['atr'][62]:.4f}")
    print(f"Pyo3 sl_pct_price_short at 63: {pyo3_df['sl_pct_price_short'][63]:.4f}")


if __name__ == "__main__":
    main()
