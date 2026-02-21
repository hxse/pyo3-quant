"""
Walk-Forward 关键防回归测试。

目标：
1. 防止 stitched 资金曲线在窗口边界出现“无事件断崖”；
2. 验证单窗口退化场景下 stitched 与窗口 test 结果等价；
3. 验证无交易场景下 stitched 资金曲线保持不变。
"""

from __future__ import annotations

import math

from py_entry.Test.shared.constants import TEST_START_TIME_MS
from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    OptimizeMetric,
    OptimizerConfig,
    Param,
    ParamType,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
    WalkForwardConfig,
)


def _build_backtest(*, num_bars: int, no_trade: bool = False) -> Backtest:
    """构建测试用 Backtest（小数据、固定种子，保证速度与复现）。"""
    base_key = "ohlcv_15m"
    data_cfg = DataGenerationParams(
        timeframes=["15m"],
        start_time=TEST_START_TIME_MS,
        num_bars=num_bars,
        base_data_key=base_key,
        fixed_seed=42,
        allow_gaps=False,
    )

    indicators = {
        base_key: {
            "sma_fast": {
                "period": Param(
                    12,
                    min=8,
                    max=20,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                )
            },
            "sma_slow": {
                "period": Param(
                    48,
                    min=24,
                    max=96,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                )
            },
        }
    }

    if no_trade:
        # 中文注释：构造恒不触发条件，确保整个流程没有任何交易。
        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"close, {base_key}, 0 > 1000000000"],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"close, {base_key}, 0 < -1000000000"],
            ),
            exit_long=None,
            exit_short=None,
        )
    else:
        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"sma_fast, {base_key}, 0 x> sma_slow, {base_key}, 0"],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"sma_fast, {base_key}, 0 x< sma_slow, {base_key}, 0"],
            ),
            exit_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"sma_fast, {base_key}, 0 x< sma_slow, {base_key}, 0"],
            ),
            exit_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"sma_fast, {base_key}, 0 x> sma_slow, {base_key}, 0"],
            ),
        )

    backtest = BacktestParams(
        initial_capital=10_000.0,
        fee_fixed=0.0,
        fee_pct=0.001,
        sl_exit_in_bar=False,
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
    )

    settings = SettingContainer(
        execution_stage=ExecutionStage.Performance,
        return_only_final=False,
    )

    return Backtest(
        enable_timing=False,
        data_source=data_cfg,
        indicators=indicators,
        signal={},
        backtest=backtest,
        signal_template=template,
        engine_settings=settings,
    )


def _build_wf_cfg(
    *, train_bars: int, transition_bars: int, test_bars: int
) -> WalkForwardConfig:
    """构建小采样 WF 配置，保证测试速度。"""
    return WalkForwardConfig(
        train_bars=train_bars,
        transition_bars=transition_bars,
        test_bars=test_bars,
        optimizer_config=OptimizerConfig(
            min_samples=12,
            max_samples=24,
            samples_per_round=6,
            stop_patience=2,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
            seed=42,
        ),
    )


def _is_nan(v: float) -> bool:
    """统一 NaN 判定，避免测试代码重复。"""
    return isinstance(v, float) and math.isnan(v)


def test_wf_boundary_no_event_no_cliff():
    """边界无进出场事件时，stitched 资金曲线不应出现断崖跳变。"""
    bt = _build_backtest(num_bars=1_400, no_trade=False)
    wf = bt.walk_forward(
        _build_wf_cfg(train_bars=400, transition_bars=100, test_bars=200)
    )

    stitched = wf.stitched_summary.backtest_result
    assert stitched is not None
    equity = stitched["equity"].to_list()
    entry_long = stitched["entry_long_price"].to_list()
    exit_long = stitched["exit_long_price"].to_list()
    entry_short = stitched["entry_short_price"].to_list()
    exit_short = stitched["exit_short_price"].to_list()

    # 中文注释：按窗口 test 段长度累计边界起点（第 2 窗口开始）。
    boundaries: list[int] = []
    acc = 0
    for idx, w in enumerate(wf.window_results):
        window_backtest = w.summary.backtest_result
        assert window_backtest is not None
        h = window_backtest.height
        if idx > 0:
            boundaries.append(acc)
        acc += h

    checked = 0
    for b in boundaries:
        if b <= 0 or b >= len(equity):
            continue

        # 中文注释：仅在边界行没有任何进出场事件时检查连续性。
        has_event = any(
            not _is_nan(v)
            for v in (entry_long[b], exit_long[b], entry_short[b], exit_short[b])
        )
        if has_event:
            continue

        prev_eq = equity[b - 1]
        curr_eq = equity[b]
        if prev_eq > 0:
            jump = abs(curr_eq / prev_eq - 1.0)
            assert jump < 1e-10, f"边界出现无事件资金跳变: idx={b}, jump={jump}"
        checked += 1

    assert checked > 0, "测试未覆盖到“无事件边界”，请调整测试数据或参数。"


def test_wf_single_window_degenerate_equivalence():
    """单窗口退化场景：stitched 与窗口 test 结果应等价。"""
    bt = _build_backtest(num_bars=700, no_trade=False)
    wf = bt.walk_forward(
        _build_wf_cfg(train_bars=400, transition_bars=100, test_bars=200)
    )

    assert len(wf.window_results) == 1
    stitched_df = wf.stitched_summary.backtest_result
    window_df = wf.window_results[0].summary.backtest_result
    assert stitched_df is not None and window_df is not None
    assert stitched_df.height == window_df.height

    # 中文注释：比较关键资金列，允许极小浮点误差。
    for col in ["balance", "equity", "total_return_pct", "fee_cum", "current_drawdown"]:
        a = stitched_df[col].to_list()
        b = window_df[col].to_list()
        assert len(a) == len(b)
        for i, (va, vb) in enumerate(zip(a, b)):
            assert abs(float(va) - float(vb)) < 1e-9, f"{col} 不一致 at idx={i}"


def test_wf_no_trade_invariance():
    """无交易场景：stitched 资金曲线应保持初始资金不变。"""
    bt = _build_backtest(num_bars=1_200, no_trade=True)
    wf = bt.walk_forward(
        _build_wf_cfg(train_bars=400, transition_bars=100, test_bars=200)
    )

    stitched_df = wf.stitched_summary.backtest_result
    assert stitched_df is not None
    balance = stitched_df["balance"].to_list()
    equity = stitched_df["equity"].to_list()

    assert max(balance) - min(balance) < 1e-10
    assert max(equity) - min(equity) < 1e-10
    assert abs(balance[0] - 10_000.0) < 1e-10
    assert abs(equity[0] - 10_000.0) < 1e-10

    agg = wf.aggregate_test_metrics
    assert abs(float(agg.get("total_return", 0.0))) < 1e-12
    assert abs(float(agg.get("max_drawdown", 0.0))) < 1e-12
    assert abs(float(agg.get("total_trades", 0.0))) < 1e-12


def test_wf_reproducibility_same_seed_same_result():
    """同配置同 seed 连续运行两次，结果应保持一致。"""
    cfg = _build_wf_cfg(train_bars=400, transition_bars=100, test_bars=200)
    bt1 = _build_backtest(num_bars=1_200, no_trade=False)
    bt2 = _build_backtest(num_bars=1_200, no_trade=False)

    wf1 = bt1.walk_forward(cfg)
    wf2 = bt2.walk_forward(cfg)

    # 中文注释：先比较聚合指标，确保高层结果一致。
    m1 = wf1.aggregate_test_metrics
    m2 = wf2.aggregate_test_metrics
    for key in ["total_return", "max_drawdown", "calmar_ratio_raw", "total_trades"]:
        assert abs(float(m1.get(key, 0.0)) - float(m2.get(key, 0.0))) < 1e-12

    # 中文注释：再比较 stitched 资金曲线，确保细粒度结果一致。
    s1 = wf1.stitched_summary.backtest_result
    s2 = wf2.stitched_summary.backtest_result
    assert s1 is not None and s2 is not None
    eq1 = s1["equity"].to_list()
    eq2 = s2["equity"].to_list()
    assert len(eq1) == len(eq2)
    for i, (v1, v2) in enumerate(zip(eq1, eq2)):
        assert abs(float(v1) - float(v2)) < 1e-12, f"equity 不一致 at idx={i}"


def test_wf_window_order_and_stitched_bars_consistent():
    """窗口顺序与 stitched 长度必须一致，防止窗口拼接错位。"""
    bt = _build_backtest(num_bars=1_400, no_trade=False)
    wf = bt.walk_forward(
        _build_wf_cfg(train_bars=400, transition_bars=100, test_bars=200)
    )

    stitched_df = wf.stitched_summary.backtest_result
    assert stitched_df is not None
    stitched_h = stitched_df.height

    sum_h = 0
    prev_test_end: int | None = None
    prev_window_id: int | None = None

    for w in wf.window_results:
        w_df = w.summary.backtest_result
        assert w_df is not None
        sum_h += w_df.height

        # 中文注释：窗口必须按自然时间顺序返回（window_id 与 test_range 都应单调）。
        if prev_window_id is not None:
            assert w.window_id > prev_window_id
        if prev_test_end is not None:
            assert w.test_range[0] >= prev_test_end
        prev_window_id = w.window_id
        prev_test_end = w.test_range[1]

    assert stitched_h == sum_h, "stitched bars 与窗口 test bars 累计不一致"
    assert int(wf.stitched_result.bars) == stitched_h


def test_wf_stitched_time_strictly_increasing():
    """stitched 时间列必须严格递增且无重复。"""
    bt = _build_backtest(num_bars=1_000, no_trade=False)
    wf = bt.walk_forward(
        _build_wf_cfg(train_bars=300, transition_bars=100, test_bars=200)
    )

    data = wf.stitched_result.data
    base_key = "ohlcv_15m"
    time_col = data.source[base_key]["time"].to_list()
    assert len(time_col) > 1

    # 中文注释：严格递增意味着“无重复 + 无逆序”。
    for i in range(1, len(time_col)):
        assert int(time_col[i]) > int(time_col[i - 1]), f"time 非严格递增 at idx={i}"
