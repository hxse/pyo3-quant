"""
调试 allow_gaps=False 时 Pyo3 和 BTP 分歧的根本原因

关键问题：当没有跳空时，两者的离场价格应该在 SL/TP 触发时完全一致，
但实际上存在分歧。需要定位是哪个交易的哪个环节出现了差异。
"""

import sys

sys.path.insert(0, "/home/hxse/pyo3-quant")

import polars as pl
import pandas as pd
import numpy as np

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.btp import ReversalExtremeBtp


def extract_pyo3_trades(pyo3_df: pl.DataFrame) -> list[dict]:
    """从 Pyo3 结果中提取交易记录"""
    if "bar_index" not in pyo3_df.columns:
        pyo3_df = pyo3_df.with_row_index("bar_index")

    trades = []
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
            in_bar = row.get("risk_in_bar_direction", 0)

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
                current_trade["InBar"] = in_bar != 0
                trades.append(current_trade)
                current_trade = None

    return trades


def main():
    # 1. 设置配置
    config = build_config_from_strategy("reversal_extreme", bars=500, seed=42)

    print("=== 配置 ===")
    print(f"bars: {config.bars}")
    print(f"seed: {config.seed}")
    print(f"allow_gaps: {config.allow_gaps}")
    print()

    # 2. 运行 Pyo3
    print("运行 Pyo3...")
    pyo3_adapter = Pyo3Adapter(config)
    pyo3_adapter.run("reversal_extreme")

    assert pyo3_adapter.result is not None
    assert pyo3_adapter.runner is not None

    pyo3_df = pyo3_adapter.result.backtest_df

    # 3. 提取共享数据给 BTP
    print("提取共享数据给 BTP...")
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

    # 4. 验证无跳空
    shift_close = ohlcv_df["Close"].shift(1)
    diff = (ohlcv_df["Open"] - shift_close).abs()
    gaps = diff[diff > 1e-6]
    print(f"检测到跳空数量: {len(gaps)}")
    if len(gaps) > 0:
        print("警告: 数据存在跳空!")
        print(gaps.head())
    print()

    # 5. 运行 BTP
    print("运行 BTP...")
    btp_adapter = BacktestingPyAdapter(config)
    btp_adapter.run(ohlcv_df, ReversalExtremeBtp)

    assert btp_adapter.result is not None
    assert btp_adapter.result.stats is not None

    btp_trades = btp_adapter.result.stats["_trades"]

    # 6. 提取 Pyo3 交易
    pyo3_trades = extract_pyo3_trades(pyo3_df)

    print(f"Pyo3 交易数: {len(pyo3_trades)}")
    print(f"BTP 交易数: {len(btp_trades)}")
    print()

    # 7. 逐笔对比交易 - 使用 EntryBar 匹配
    print("=== 逐笔交易对比 (按 EntryBar 匹配) ===")
    print(
        f"{'#':<3} {'Entry':<6} {'Exit':<6} {'Side':<6} {'P3 EntryP':<10} {'BT EntryP':<10} {'P3 ExitP':<10} {'BT ExitP':<10} {'ExitP Diff':<10} {'P3 InBar':<8}"
    )
    print("-" * 100)

    # 创建 BTP 按 EntryBar 的索引
    btp_by_entry = {}
    for i, bt in btp_trades.iterrows():
        entry_bar = bt["EntryBar"]
        if entry_bar not in btp_by_entry:
            btp_by_entry[entry_bar] = []
        btp_by_entry[entry_bar].append(bt)

    first_divergence = None
    matched_count = 0
    unmatched_pyo3 = []

    for i, pt in enumerate(pyo3_trades):
        entry_bar = pt["EntryBar"]
        if entry_bar in btp_by_entry and btp_by_entry[entry_bar]:
            bt = btp_by_entry[entry_bar].pop(0)
            matched_count += 1

            entry_diff = abs(pt["EntryPrice"] - bt["EntryPrice"])
            exit_diff = abs(pt["ExitPrice"] - bt["ExitPrice"])

            # 标记分歧
            marker = ""
            if entry_diff > 0.01 or exit_diff > 0.01:
                marker = f"<< DIFF (entry:{entry_diff:.4f}, exit:{exit_diff:.4f})"
                if first_divergence is None:
                    first_divergence = (i, pt, bt)

            print(
                f"{i:<3} {pt['EntryBar']:<6} {pt['ExitBar']:<6} {pt['Side']:<6} "
                f"{pt['EntryPrice']:<10.4f} {bt['EntryPrice']:<10.4f} "
                f"{pt['ExitPrice']:<10.4f} {bt['ExitPrice']:<10.4f} "
                f"{exit_diff:<10.4f} {str(pt['InBar']):<8} {marker}"
            )
        else:
            unmatched_pyo3.append(pt)
            print(
                f"{i:<3} {pt['EntryBar']:<6} {pt['ExitBar']:<6} {pt['Side']:<6} "
                f"{pt['EntryPrice']:<10.4f} {'N/A':<10} "
                f"{pt['ExitPrice']:<10.4f} {'N/A':<10} "
                f"{'N/A':<10} {str(pt['InBar']):<8} << NO MATCH"
            )
    print()

    # 8. 分析第一个分歧
    if first_divergence is not None:
        div_idx, pt, bt = first_divergence
        print(f"=== 第一个分歧: 交易 #{div_idx} ===")

        entry_bar = pt["EntryBar"]
        exit_bar = pt["ExitBar"]

        print(f"Pyo3 Entry: Bar {entry_bar}, Price {pt['EntryPrice']:.4f}")
        print(f"BTP  Entry: Bar {bt['EntryBar']}, Price {bt['EntryPrice']:.4f}")
        print(
            f"Pyo3 Exit:  Bar {exit_bar}, Price {pt['ExitPrice']:.4f}, InBar={pt['InBar']}"
        )
        print(f"BTP  Exit:  Bar {bt['ExitBar']}, Price {bt['ExitPrice']:.4f}")
        print(f"BTP  SL:    {bt['SL']:.4f}")
        print(f"BTP  TP:    {bt['TP']:.4f}")
        print()

        # 查看离场 Bar 的 OHLC
        print(f"Exit Bar {exit_bar} OHLC:")
        exit_row = ohlcv_df.iloc[exit_bar]
        print(f"  Open:  {exit_row['Open']:.4f}")
        print(f"  High:  {exit_row['High']:.4f}")
        print(f"  Low:   {exit_row['Low']:.4f}")
        print(f"  Close: {exit_row['Close']:.4f}")
        print()

        # 分析差异原因
        if pt["InBar"]:
            print("分析: Pyo3 使用 In-Bar 模式 (exit_in_bar=True)")
            if pt["Side"] == "Long":
                print(f"  对于多头止损，Pyo3 成交价 = SL 价格 = {pt['ExitPrice']:.4f}")
                print(
                    f"  BTP 成交价 = min(Open, SL) = min({exit_row['Open']:.4f}, {bt['SL']:.4f}) = {bt['ExitPrice']:.4f}"
                )
            else:
                print(f"  对于空头止损，Pyo3 成交价 = SL 价格 = {pt['ExitPrice']:.4f}")
                print(
                    f"  BTP 成交价 = max(Open, SL) = max({exit_row['Open']:.4f}, {bt['SL']:.4f}) = {bt['ExitPrice']:.4f}"
                )

            if abs(pt["ExitPrice"] - bt["SL"]) < 0.01:
                print("  结论: Pyo3 使用 SL 价格作为成交价，而 BTP 考虑了跳空滑点")
    else:
        print("未发现显著分歧!")

    # 9. 最终净值对比
    print()
    print("=== 最终净值对比 ===")
    pyo3_final = pyo3_adapter.get_equity_curve()[-1]
    btp_final = btp_adapter.get_equity_curve()[-1]
    print(f"Pyo3 最终净值: {pyo3_final:.2f}")
    print(f"BTP  最终净值: {btp_final:.2f}")
    print(f"差异: {abs(pyo3_final - btp_final):.2f}")


if __name__ == "__main__":
    main()
