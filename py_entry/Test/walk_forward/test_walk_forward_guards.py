"""
Walk-Forward 关键防回归测试。

目标：
1. 防止 stitched 资金曲线在窗口边界出现“无事件断崖”；
2. 验证单窗口退化场景下 stitched 与窗口 test 结果等价；
3. 验证无交易场景下 stitched 资金曲线保持不变。
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import pytest

from py_entry.Test.shared.constants import TEST_START_TIME_MS
from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.runner import FormatResultsConfig
from py_entry.types import (
    ExecutionStage,
    HorizontalLineLayoutItem,
    LogicOp,
    Param,
    ParamType,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
    WalkForwardConfig,
)


def _window_active_backtest(window) -> pl.DataFrame:
    """从窗口正式 test_pack_result 中切出 active-only backtest。"""
    backtest_df = window.test_pack_result.backtest_result
    assert backtest_df is not None
    base_key = window.test_pack_result.base_data_key
    base_range = window.test_pack_result.ranges[base_key]
    return backtest_df.slice(base_range.warmup_bars, base_range.active_bars)


@pytest.fixture(scope="module")
def wf_default(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """复用默认 WF 场景，避免重复构建大对象。"""
    bt = build_sma_cross_backtest(
        num_bars=1_400,
        no_trade=False,
        with_backtest_params=True,
    )
    cfg = build_wf_cfg(
        train_active_bars=400,
        test_active_bars=200,
        min_warmup_bars=100,
        optimizer_rounds=24,
    )
    return bt.walk_forward(cfg)


def test_wf_boundary_no_event_no_cliff(
    wf_default,
    missing_expr: Callable[[str], pl.Expr],
):
    """边界无进出场事件时，stitched 资金曲线不应出现断崖跳变。"""
    wf = wf_default

    stitched = wf.stitched_pack_result.backtest_result
    assert stitched is not None
    equity = stitched["equity"].cast(pl.Float64, strict=False)
    event_mask = stitched.select(
        pl.any_horizontal(
            [
                ~missing_expr("entry_long_price"),
                ~missing_expr("exit_long_price"),
                ~missing_expr("entry_short_price"),
                ~missing_expr("exit_short_price"),
            ]
        ).alias("__has_event")
    )["__has_event"].cast(pl.Boolean, strict=False)

    # 中文注释：按窗口 test 段长度累计边界起点（第 2 窗口开始）。
    boundaries: list[int] = []
    acc = 0
    for idx, w in enumerate(wf.window_results):
        h = _window_active_backtest(w).height
        if idx > 0:
            boundaries.append(acc)
        acc += h

    checked = 0
    for b in boundaries:
        if b <= 0 or b >= equity.len():
            continue

        # 中文注释：仅在边界行没有任何进出场事件时检查连续性。
        has_event = bool(event_mask[b])
        if has_event:
            continue

        prev_eq = float(equity[b - 1])
        curr_eq = float(equity[b])
        if prev_eq > 0:
            jump = abs(curr_eq / prev_eq - 1.0)
            assert jump < 1e-10, f"边界出现无事件资金跳变: idx={b}, jump={jump}"
        checked += 1

    assert checked > 0, "测试未覆盖到“无事件边界”，请调整测试数据或参数。"


def test_wf_single_window_degenerate_equivalence(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """单窗口退化场景：stitched 与窗口 test 结果应等价。"""
    bt = build_sma_cross_backtest(
        num_bars=700,
        no_trade=False,
        with_backtest_params=True,
    )
    wf = bt.walk_forward(
        build_wf_cfg(
            train_active_bars=400,
            test_active_bars=200,
            min_warmup_bars=100,
            optimizer_rounds=24,
        )
    )

    assert len(wf.window_results) == 1
    stitched_df = wf.stitched_pack_result.backtest_result
    window_df = _window_active_backtest(wf.window_results[0])
    assert stitched_df is not None
    assert stitched_df.height == window_df.height

    # 中文注释：比较关键资金列，使用向量化差值最大值断言。
    for col in ["balance", "equity", "total_return_pct", "fee_cum", "current_drawdown"]:
        a = stitched_df[col].cast(pl.Float64, strict=False)
        b = window_df[col].cast(pl.Float64, strict=False)
        assert len(a) == len(b)
        max_diff = float((a - b).abs().max() or 0.0)
        assert max_diff < 1e-9, f"{col} 不一致, max_diff={max_diff}"


def test_wf_no_trade_invariance(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """无交易场景：stitched 资金曲线应保持初始资金不变。"""
    bt = build_sma_cross_backtest(
        num_bars=1_200,
        no_trade=True,
        with_backtest_params=True,
    )
    wf = bt.walk_forward(
        build_wf_cfg(
            train_active_bars=400,
            test_active_bars=200,
            min_warmup_bars=100,
            optimizer_rounds=24,
        )
    )

    stitched_df = wf.stitched_pack_result.backtest_result
    assert stitched_df is not None
    balance = stitched_df["balance"].cast(pl.Float64, strict=False)
    equity = stitched_df["equity"].cast(pl.Float64, strict=False)

    assert float((balance.max() or 0.0) - (balance.min() or 0.0)) < 1e-10
    assert float((equity.max() or 0.0) - (equity.min() or 0.0)) < 1e-10
    assert abs(float(balance[0]) - 10_000.0) < 1e-10
    assert abs(float(equity[0]) - 10_000.0) < 1e-10

    agg = wf.aggregate_test_metrics
    assert abs(float(agg.get("total_return", 0.0))) < 1e-12
    assert abs(float(agg.get("max_drawdown", 0.0))) < 1e-12
    assert abs(float(agg.get("total_trades", 0.0))) < 1e-12


def test_wf_reproducibility_same_seed_same_result(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """同配置同 seed 连续运行两次，结果应保持一致（2000 bars + 20 次优化）。"""
    cfg = build_wf_cfg(
        train_active_bars=500,
        test_active_bars=200,
        min_warmup_bars=150,
        optimizer_rounds=20,
    )
    bt1 = build_sma_cross_backtest(
        num_bars=2_000,
        no_trade=False,
        with_backtest_params=True,
    )
    bt2 = build_sma_cross_backtest(
        num_bars=2_000,
        no_trade=False,
        with_backtest_params=True,
    )

    wf1 = bt1.walk_forward(cfg)
    wf2 = bt2.walk_forward(cfg)

    # 中文注释：先比较聚合指标，确保高层结果一致。
    m1 = wf1.aggregate_test_metrics
    m2 = wf2.aggregate_test_metrics
    for key in ["total_return", "max_drawdown", "calmar_ratio_raw", "total_trades"]:
        assert abs(float(m1.get(key, 0.0)) - float(m2.get(key, 0.0))) < 1e-12

    # 中文注释：再比较 stitched 资金曲线，向量化检查最大差值为 0。
    s1 = wf1.stitched_pack_result.backtest_result
    s2 = wf2.stitched_pack_result.backtest_result
    assert s1 is not None and s2 is not None
    eq1 = s1["equity"].cast(pl.Float64, strict=False)
    eq2 = s2["equity"].cast(pl.Float64, strict=False)
    assert len(eq1) == len(eq2)
    max_diff = float((eq1 - eq2).abs().max() or 0.0)
    assert max_diff < 1e-12, f"equity 不一致, max_diff={max_diff}"


def test_wf_window_order_and_stitched_bars_consistent(wf_default):
    """窗口顺序与 stitched 长度必须一致，防止窗口拼接错位。"""
    wf = wf_default

    stitched_df = wf.stitched_pack_result.backtest_result
    assert stitched_df is not None
    stitched_h = stitched_df.height

    sum_h = 0
    prev_test_end: int | None = None
    prev_window_id: int | None = None

    for w in wf.window_results:
        sum_h += _window_active_backtest(w).height

        # 中文注释：窗口必须按自然时间顺序返回（window_id 与 test_active_base_row_range 都应单调）。
        if prev_window_id is not None:
            assert w.meta.window_id > prev_window_id
        if prev_test_end is not None:
            assert w.meta.test_active_base_row_range[0] >= prev_test_end
        prev_window_id = w.meta.window_id
        prev_test_end = w.meta.test_active_base_row_range[1]

    assert stitched_h == sum_h, "stitched bars 与窗口 test bars 累计不一致"
    assert int(wf.stitched_result.stitched_data.mapping.height) == stitched_h


def test_wf_stitched_time_strictly_increasing(wf_default, wf_base_key: str):
    """stitched 时间列必须严格递增且无重复。"""
    wf = wf_default

    data = wf.stitched_result.stitched_data
    time_col = data.source[wf_base_key]["time"].cast(pl.Int64, strict=False)
    assert len(time_col) > 1
    # 中文注释：严格递增等价于差分最小值大于 0。
    min_step = int(time_col.diff().drop_nulls().min() or 0)
    assert min_step > 0, f"time 非严格递增, min_step={min_step}"


def test_wf_stitched_export_uses_backtest_schedule_not_single_param_set(wf_default):
    """stitched 导出必须以 segmented replay schedule 为正式参数解释层。"""
    wf = wf_default.format_for_export(FormatResultsConfig(dataframe_format="csv"))
    assert wf.export_buffers is not None

    exported_paths = {str(path) for path, _ in wf.export_buffers}
    assert "backtest_schedule/backtest_schedule.json" in exported_paths
    assert "param_set/param.json" not in exported_paths


def test_wf_stitched_indicator_layout_rejects_param_key_hline(wf_default):
    """stitched 默认图表生成不得再借用单窗口参数解释 paramKey 型 hline。"""
    with pytest.raises(ValueError, match="paramKey 型 hline"):
        wf_default.format_for_export(
            FormatResultsConfig(
                dataframe_format="csv",
                indicator_layout={
                    "main": [
                        HorizontalLineLayoutItem(
                            indicator="signal_threshold",
                            paramKey="signal_threshold",
                            anchorIndicator="sma_fast",
                        )
                    ]
                },
            )
        )


def test_wf_boundary_cross_inheritance_not_reset_to_initial(
    wf_base_key: str,
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """跨窗继承场景下，窗口边界资金不得异常重置到初始资金。"""
    data_cfg = DataGenerationParams(
        timeframes=["15m"],
        start_time=TEST_START_TIME_MS,
        num_bars=600,
        base_data_key=wf_base_key,
        fixed_seed=42,
        allow_gaps=False,
    )

    # 中文注释：WF 入口当前要求存在 base source 的指标聚合结果，这里放一个最小指标满足约束。
    indicators = {
        wf_base_key: {
            "sma_anchor": {
                "period": Param(
                    1,
                    min=1,
                    max=2,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                )
            }
        }
    }

    # 中文注释：构造恒开仓模板以稳定产生跨窗继承。
    template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[f"close, {wf_base_key}, 0 > -1"],
        ),
        entry_short=None,
        exit_long=None,
        exit_short=None,
    )
    settings = SettingContainer(
        execution_stage=ExecutionStage.Performance,
        return_only_final=False,
    )
    bt = Backtest(
        enable_timing=False,
        data_source=data_cfg,
        indicators=indicators,
        signal={},
        signal_template=template,
        engine_settings=settings,
    )
    # 中文注释：用较小优化轮次和适中的 test_active_bars，保持跨窗继承语义同时显著降低窗口总数。
    wf = bt.walk_forward(
        build_wf_cfg(
            train_active_bars=200,
            test_active_bars=20,
            min_warmup_bars=30,
            optimizer_rounds=6,
        )
    )
    stitched = wf.stitched_pack_result.backtest_result
    assert stitched is not None
    equity = stitched["equity"].cast(pl.Float64, strict=False)

    initial_capital = 10_000.0
    acc = 0
    checked = 0
    for idx, w in enumerate(wf.window_results):
        w_df = _window_active_backtest(w)
        if idx > 0 and bool(w.meta.has_cross_boundary_position):
            b = acc
            if 0 <= b < equity.len():
                assert abs(float(equity[b]) - initial_capital) > 1e-9, (
                    f"跨窗继承边界资金异常重置到初始值: window={idx}, idx={b}"
                )
                checked += 1
        acc += w_df.height

    if checked == 0:
        pytest.skip("当前数据/参数未触发跨窗继承，跳过该断言分支。")
