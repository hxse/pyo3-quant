"""
调试 allow_gaps=False 时 Pyo3 和 BTP 交易数量分歧的原因
"""

import numpy as np
import polars as pl
from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def run_debug():
    # 使用 allow_gaps=False, num_bars=6000 配置
    config = CommonConfig(
        bars=6000,
        seed=42,
        initial_capital=10000.0,
        commission=0.001,
        timeframe="15m",
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        allow_gaps=False,  # 关键：禁用跳空
        equity_cutoff_ratio=0.20,
    )

    print(f"=== 调试配置 ===")
    print(f"bars: {config.bars}, allow_gaps: {config.allow_gaps}")

    # 1. 运行 Pyo3
    print("\n[1/2] 运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")
    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None
    assert pyo3_adapter.runner.data_dict is not None

    pyo3_df = pyo3_adapter.result.backtest_df.with_row_index("bar_index")

    # 找出进场 Bar
    pyo3_long_entries = pyo3_df.filter(pl.col("entry_long_price").is_not_nan())
    pyo3_short_entries = pyo3_df.filter(pl.col("entry_short_price").is_not_nan())

    pyo3_long_bars = set(pyo3_long_entries["bar_index"].to_list())
    pyo3_short_bars = set(pyo3_short_entries["bar_index"].to_list())
    pyo3_all_entry_bars = pyo3_long_bars | pyo3_short_bars

    print(f"  Pyo3 Long 进场数: {len(pyo3_long_bars)}")
    print(f"  Pyo3 Short 进场数: {len(pyo3_short_bars)}")
    print(f"  Pyo3 总进场数: {len(pyo3_all_entry_bars)}")

    # 2. 运行 BTP
    print("\n[2/2] 运行 BTP...")
    ohlcv_df = generate_ohlcv_for_backtestingpy(config)
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)
    assert btp_adapter.result is not None

    # 从 stats['_trades'] 获取交易记录
    btp_trades_df = btp_adapter.result.stats["_trades"]
    btp_long_bars = set()
    btp_short_bars = set()
    for _, row in btp_trades_df.iterrows():
        entry_bar = row["EntryBar"]
        size = row["Size"]
        if size > 0:
            btp_long_bars.add(entry_bar)
        else:
            btp_short_bars.add(entry_bar)
    btp_all_entry_bars = btp_long_bars | btp_short_bars

    print(f"  BTP Long 进场数: {len(btp_long_bars)}")
    print(f"  BTP Short 进场数: {len(btp_short_bars)}")
    print(f"  BTP 总进场数: {len(btp_all_entry_bars)}")

    # 3. 分析交易差异
    print("\n=== 交易差异分析 ===")
    missing_in_pyo3 = sorted(btp_all_entry_bars - pyo3_all_entry_bars)
    missing_in_btp = sorted(pyo3_all_entry_bars - btp_all_entry_bars)

    print(f"BTP 有但 Pyo3 没有的进场: {len(missing_in_pyo3)} 笔")
    print(f"Pyo3 有但 BTP 没有的进场: {len(missing_in_btp)} 笔")

    # 4. 获取 OHLCV 数据
    base_key = f"ohlcv_{config.timeframe}"
    pyo3_source = pyo3_adapter.runner.data_dict.source[base_key]

    open_arr = pyo3_source["open"].to_numpy()
    close_arr = pyo3_source["close"].to_numpy()

    # 5. 分析 BTP 有但 Pyo3 没有的交易
    if len(missing_in_pyo3) > 0:
        print(f"\n=== 分析 BTP 有但 Pyo3 缺失的前 15 笔交易 ===")

        gap_fail_count = 0

        for i, entry_bar in enumerate(missing_in_pyo3[:15]):
            signal_bar = entry_bar - 1
            if signal_bar < 0:
                continue

            signal_close = close_arr[signal_bar]
            entry_open = open_arr[entry_bar]

            direction = "Long" if entry_bar in btp_long_bars else "Short"

            # 计算 SL 价格 (sl_pct = 0.02)
            sl_pct = 0.02
            if direction == "Long":
                sl_price = signal_close * (1 - sl_pct)
                is_gap_safe = entry_open >= sl_price
            else:
                sl_price = signal_close * (1 + sl_pct)
                is_gap_safe = entry_open <= sl_price

            print(f"\n[{i + 1}] Entry Bar {entry_bar} ({direction})")
            print(f"    Signal Close: {signal_close:.4f}")
            print(
                f"    Entry Open: {entry_open:.4f} (should == Signal Close: {abs(entry_open - signal_close) < 0.0001})"
            )
            print(f"    SL Price (2%): {sl_price:.4f}")
            print(f"    Gap Check: {'PASS' if is_gap_safe else 'FAIL'}")

            if not is_gap_safe:
                print(f"    *** Pyo3 因 gap_check 拒绝! ***")
                gap_fail_count += 1
            else:
                # 检查 Pyo3 在这个 Bar 的状态
                pyo3_row = pyo3_df.filter(pl.col("bar_index") == entry_bar)
                if len(pyo3_row) > 0:
                    first_entry_side = pyo3_row["first_entry_side"][0]
                    print(f"    Pyo3 first_entry_side: {first_entry_side}")
                    if first_entry_side == 0:
                        print(f"    *** Pyo3 没有产生进场信号! 可能是信号逻辑差异 ***")
                    else:
                        print(f"    *** 信号存在但未进场，需检查其他风控逻辑 ***")

        print(f"\n前 15 笔中因 Gap Check 失败: {gap_fail_count}")
        if gap_fail_count == 0:
            print("*** Gap Check 不是问题根源！交易差异来自信号逻辑或其他地方 ***")


if __name__ == "__main__":
    run_debug()
