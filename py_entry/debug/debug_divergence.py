import dataclasses
import numpy as np
import pandas as pd
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies import get_strategy


def debug_divergence():
    strategy_name = "reversal_extreme"
    print(f"开始深入排查: {strategy_name} (6000 bars)")

    # 强制配置 6000 bars
    config = build_config_from_strategy("reversal_extreme")
    config.bars = 6000
    config.timeframe = "15m"
    config.start_time = 1735689600000
    config.seed = 42
    config.initial_capital = 10000.0

    # 1. 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run(strategy_name)
    pyo3_equity = pyo3_adapter.get_equity_curve()

    # 2. 运行 Btp
    print("运行 Backtesting.py...")
    strategy_config = get_strategy(strategy_name)
    ohlcv_df = generate_ohlcv_for_backtestingpy(config)
    btp_adapter = BacktestingPyAdapter(config)
    assert strategy_config.btp_strategy_class is not None
    btp_adapter.run(ohlcv_df, strategy_config.btp_strategy_class)
    btp_equity = btp_adapter.get_equity_curve()

    # 3. 对齐长度
    min_len = min(len(pyo3_equity), len(btp_equity))
    pyo3_equity = pyo3_equity[:min_len]
    btp_equity = btp_equity[:min_len]
    ohlcv_df = ohlcv_df.iloc[:min_len]

    # 4. 寻找分歧点
    # 定义分歧：两者净值差超过初始本金的 5% (500)
    diff = np.abs(pyo3_equity - btp_equity)
    divergence_indices = np.where(diff > 500)[0]

    if len(divergence_indices) == 0:
        print("未发现显著分歧！")
        return

    first_div_idx = divergence_indices[0]
    print(f"\n发现首个显著分歧点 (Diff > 500): Bar Index {first_div_idx}")

    start_look = 60
    end_look = 70

    print("\n分歧点附近详情:")
    print(
        f"{'Idx':<6} {'Time':<20} {'Open':<8} {'High':<8} {'Low':<8} {'Close':<8} {'Pyo3 Eq':<10} {'Btp Eq':<10} {'Diff':<10}"
    )
    print("-" * 100)

    for i in range(start_look, end_look):
        time_str = str(ohlcv_df.index[i])
        row = ohlcv_df.iloc[i]
        open_p = row["Open"]
        high_p = row["High"]
        low_p = row["Low"]
        close_p = row["Close"]
        p_eq = pyo3_equity[i]
        b_eq = btp_equity[i]
        d = p_eq - b_eq
        marker = "<<" if i == first_div_idx else ""
        print(
            f"{i:<6} {time_str:<20} {open_p:<8.2f} {high_p:<8.2f} {low_p:<8.2f} {close_p:<8.2f} {p_eq:<10.2f} {b_eq:<10.2f} {d:<10.2f} {marker}"
        )

    # 打印此时的交易记录（如果有 API 支持）
    assert btp_adapter.result is not None
    assert btp_adapter.result.stats is not None
    # Backtesting.py 的 trades
    print(f"\nBacktesting.py 在 Bar {first_div_idx} 附近的交易:")
    trades = btp_adapter.result.stats["_trades"]
    # 筛选 EntryBar 或 ExitBar 在分歧点附近的交易
    nearby_trades = trades[
        (trades["EntryBar"].between(first_div_idx - 5, first_div_idx + 5))
        | (trades["ExitBar"].between(first_div_idx - 5, first_div_idx + 5))
    ]
    print(nearby_trades.to_string())

    # Pyo3 的 trades (通过 adapter 获取 df 并过滤)
    print("\nPyo3 最近的 Exit 记录:")
    assert pyo3_adapter.result is not None
    assert pyo3_adapter.result.backtest_df is not None
    pyo3_df = pyo3_adapter.result.backtest_df
    # 找到在分歧点附近的 exits
    # pyo3 df 长度也是 6000?
    # 我们只看分歧点附近的 slice
    slice_df = pyo3_df[start_look:end_look]
    print(
        slice_df.select(
            ["exit_long_price", "exit_short_price", "trade_pnl_pct", "equity"]
        )
    )


if __name__ == "__main__":
    debug_divergence()
