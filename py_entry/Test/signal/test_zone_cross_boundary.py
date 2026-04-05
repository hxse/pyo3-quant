import polars as pl
from datetime import datetime, timedelta

from py_entry.data_generator import DirectDataConfig
from py_entry.types import (
    ExecutionStage,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
)
from py_entry.Test.shared import make_backtest_runner, make_engine_settings


def _assert_bool_series_equal(
    result_slice: pl.Series | list[bool], expected: list[bool], context: str
):
    """向量化断言布尔序列一致，失败时给出首个差异位置。"""
    res_s = (
        result_slice.cast(pl.Boolean, strict=False)
        if isinstance(result_slice, pl.Series)
        else pl.Series("result", result_slice, dtype=pl.Boolean)
    )
    exp_s = pl.Series("expected", expected, dtype=pl.Boolean)
    assert res_s.len() == exp_s.len(), f"{context}: 长度不一致"

    mismatch = res_s != exp_s
    if bool(mismatch.any()):
        first_idx = int(mismatch.arg_max() or 0)
        raise AssertionError(
            f"{context}: 首个不一致索引={first_idx}, expected={exp_s[first_idx]}, got={res_s[first_idx]}"
        )


def _build_data_config(closes: list[float]) -> DirectDataConfig:
    """构造用于边界测试的精确 OHLCV 数据。"""
    padding_len = 20
    padded_closes = [closes[0]] * padding_len + closes
    start_time = datetime(2024, 1, 1)
    times = [
        int((start_time + timedelta(minutes=15 * i)).timestamp() * 1000)
        for i in range(len(padded_closes))
    ]

    df = pl.DataFrame(
        {
            "time": times,
            "open": padded_closes,
            "high": padded_closes,
            "low": padded_closes,
            "close": padded_closes,
            "volume": [1000.0] * len(padded_closes),
        }
    ).with_columns(
        pl.from_epoch(pl.col("time"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
        .alias("date")
    )

    return DirectDataConfig(data={"ohlcv_15m": df}, base_data_key="ohlcv_15m")


def _run_zone_cross_signal(comparison: str, closes: list[float]) -> pl.Series:
    """运行单条区间穿越信号，返回测试片段对应的结果。"""
    return _run_signal_template(
        SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[comparison],
            )
        ),
        closes,
    )


def _run_signal_template(
    signal_template: SignalTemplate, closes: list[float]
) -> pl.Series:
    """运行给定模板，返回测试片段对应的结果。"""
    runner = make_backtest_runner(
        data_source=_build_data_config(closes),
        indicators={"ohlcv_15m": {"sma_1": {"period": Param(1)}}},
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )

    result = runner.run()
    signals = result.result.signals
    assert signals is not None

    return signals["entry_long"].slice(
        signals["entry_long"].len() - len(closes), len(closes)
    )


def test_zone_cross_up_closed_interval():
    """
    验证 x> 进入的是闭区间：
    - 前一根在区间下方，当前进入 [low, high] 时激活
    - 触到上下边界仍保持有效
    - 只有真正跑出区间外才失效
    """
    closes = [20.0, 29.0, 30.0, 30.0, 50.0, 70.0, 71.0, 70.0, 29.0, 30.0, 70.0, 71.0]
    result_slice = _run_zone_cross_signal("sma_1 x> 30..70", closes)
    expected = [
        False,
        False,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        True,
        True,
        False,
    ]
    _assert_bool_series_equal(result_slice, expected, context="x> 30..70")


def test_zone_cross_down_closed_interval():
    """
    验证 x< 从区间上边界进入闭区间时激活，边界值本身仍属于有效区间。
    """
    closes = [80.0, 71.0, 70.0, 70.0, 50.0, 30.0, 29.0, 30.0, 80.0, 70.0, 30.0, 29.0]
    result_slice = _run_zone_cross_signal("sma_1 x< 70..30", closes)
    expected = [
        False,
        False,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
        True,
        True,
        False,
    ]
    _assert_bool_series_equal(result_slice, expected, context="x< 70..30")


def test_zone_cross_reversed_bounds_equivalent():
    """验证区间边界顺序不影响语义，方向仅由 x> / x< 决定。"""
    up_closes = [20.0, 29.0, 30.0, 50.0, 70.0, 71.0, 29.0, 30.0]
    up_normal = _run_zone_cross_signal("sma_1 x> 30..70", up_closes)
    up_reversed = _run_zone_cross_signal("sma_1 x> 70..30", up_closes)
    _assert_bool_series_equal(up_normal, up_reversed.to_list(), context="x> bounds")

    down_closes = [80.0, 71.0, 70.0, 50.0, 30.0, 29.0, 80.0, 70.0]
    down_normal = _run_zone_cross_signal("sma_1 x< 70..30", down_closes)
    down_reversed = _run_zone_cross_signal("sma_1 x< 30..70", down_closes)
    _assert_bool_series_equal(down_normal, down_reversed.to_list(), context="x< bounds")


def test_range_in_closed_interval():
    """验证 in .. 只判断当前是否位于闭区间内，边界顺序无关。"""
    closes = [20.0, 30.0, 50.0, 70.0, 71.0]
    expected = [False, True, True, True, False]
    normal = _run_zone_cross_signal("sma_1 in 30..70", closes)
    reversed_bounds = _run_zone_cross_signal("sma_1 in 70..30", closes)
    _assert_bool_series_equal(normal, expected, context="in 30..70")
    _assert_bool_series_equal(reversed_bounds, expected, context="in reversed bounds")


def test_range_xin_enters_closed_interval_once():
    """验证 xin .. 只在前一根不在区间、当前进入闭区间时触发一次。"""
    closes = [20.0, 29.0, 30.0, 30.0, 50.0, 71.0, 70.0, 69.0]
    expected = [False, False, True, False, False, False, True, False]
    normal = _run_zone_cross_signal("sma_1 xin 30..70", closes)
    reversed_bounds = _run_zone_cross_signal("sma_1 xin 70..30", closes)
    _assert_bool_series_equal(normal, expected, context="xin 30..70")
    _assert_bool_series_equal(reversed_bounds, expected, context="xin reversed bounds")


def test_range_in_matches_expanded_template():
    """验证 in .. 与普通比较组合的展开写法等价。"""
    closes = [20.0, 29.0, 30.0, 50.0, 70.0, 71.0]
    sugar = _run_zone_cross_signal("sma_1 in 30..70", closes)
    expanded = _run_signal_template(
        SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_1 >= 30", "sma_1 <= 70"],
            )
        ),
        closes,
    )
    _assert_bool_series_equal(sugar, expanded.to_list(), context="in sugar equality")


def test_range_xin_matches_expanded_template():
    """验证 xin .. 与“当前在区间内且前一根在区间外”的展开写法等价。"""
    closes = [20.0, 29.0, 30.0, 30.0, 50.0, 71.0, 70.0, 69.0]
    sugar = _run_zone_cross_signal("sma_1 xin 30..70", closes)
    expanded = _run_signal_template(
        SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_1 >= 30", "sma_1 <= 70"],
                sub_groups=[
                    SignalGroup(
                        logic=LogicOp.OR,
                        comparisons=[
                            "sma_1, ohlcv_15m, 1 < 30",
                            "sma_1, ohlcv_15m, 1 > 70",
                        ],
                    )
                ],
            )
        ),
        closes,
    )
    _assert_bool_series_equal(sugar, expanded.to_list(), context="xin sugar equality")
