import polars as pl
import pytest

from pyo3_quant import (
    DataPackFetchPlanner,
    DataPackFetchPlannerInput,
    BacktestParams,
    Param,
)


def _times(start: int, step: int, count: int) -> list[int]:
    """构造严格递增时间轴。"""
    return [start + step * i for i in range(count)]


def _ohlcv_df(times: list[int]) -> pl.DataFrame:
    """构造最小 OHLCV DataFrame。"""
    return pl.DataFrame(
        {
            "time": times,
            "open": [1.0] * len(times),
            "high": [1.0] * len(times),
            "low": [1.0] * len(times),
            "close": [1.0] * len(times),
            "volume": [1.0] * len(times),
        }
    )


def _backtest_without_exec_warmup() -> BacktestParams:
    """构造不会引入 exec warmup 的最小回测参数。"""
    return BacktestParams(
        initial_capital=10_000.0,
        fee_fixed=0.0,
        fee_pct=0.0,
        sl_exit_in_bar=False,
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        sl_pct=None,
        tp_pct=None,
        tsl_pct=None,
        sl_atr=None,
        tp_atr=None,
        tsl_atr=None,
        atr_period=None,
    )


def test_planner_source_keys_follow_unique_base_union_formula():
    """source_keys 必须唯一等于 unique({base_data_key} ∪ {'ohlcv_'+timeframe})。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m", "1h", "15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            indicators_params={"ohlcv_1h": {"sma_0": {"period": Param(5)}}},
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    assert set(planner.source_keys) == {"ohlcv_15m", "ohlcv_1h"}
    assert len(planner.source_keys) == 2


def test_planner_rejects_indicator_source_keys_outside_generated_source_keys():
    """指标 source_key 不在 source_keys 中时必须在初始化阶段直接报错。"""
    with pytest.raises(ValueError, match="不属于 planner source_keys"):
        DataPackFetchPlanner(
            DataPackFetchPlannerInput(
                timeframes=["15m", "1h"],
                base_data_key="ohlcv_15m",
                effective_since=0,
                effective_limit=3,
                indicators_params={"ohlcv_4h": {"sma_0": {"period": Param(5)}}},
                backtest_params=_backtest_without_exec_warmup(),
            )
        )


def test_planner_rejects_invalid_source_interval_key_during_init():
    """任一 source_key 解析不到合法 interval_ms 时必须在初始化阶段 fail-fast。"""
    with pytest.raises(ValueError, match=r"source_key 'ohlcv_bad'"):
        DataPackFetchPlanner(
            DataPackFetchPlannerInput(
                timeframes=["15m", "bad"],
                base_data_key="ohlcv_15m",
                effective_since=0,
                effective_limit=3,
                backtest_params=_backtest_without_exec_warmup(),
            )
        )


def test_planner_rejects_short_base_effective_df():
    """base 首次响应非空但不足 effective_limit 时必须直接 fail-fast。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    request = planner.next_request()
    assert request is not None
    assert request.source_key == "ohlcv_15m"
    assert request.limit == 3

    with pytest.raises(ValueError, match="height\\(\\)=2 < effective_limit=3"):
        planner.ingest_response(request, _ohlcv_df([0, 900_000]))


def test_planner_finish_returns_datapack_after_base_and_source_complete():
    """最小 happy path：planner 完成后必须统一回收到 DataPack。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m", "1h"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    base_request = planner.next_request()
    assert base_request is not None
    planner.ingest_response(base_request, _ohlcv_df([0, 900_000, 1_800_000]))

    source_request = planner.next_request()
    assert source_request is not None
    assert source_request.source_key == "ohlcv_1h"
    planner.ingest_response(source_request, _ohlcv_df([0, 3_600_000]))

    assert planner.is_complete() is True
    assert planner.next_request() is None

    data_pack = planner.finish()
    assert data_pack.base_data_key == "ohlcv_15m"
    assert set(data_pack.source.keys()) == {"ohlcv_15m", "ohlcv_1h"}
    assert data_pack.ranges["ohlcv_15m"].warmup_bars == 0
    assert data_pack.ranges["ohlcv_15m"].active_bars == 3
    assert data_pack.ranges["ohlcv_1h"].warmup_bars == 0
    assert data_pack.ranges["ohlcv_1h"].active_bars == 2


def test_planner_finish_fails_fast_before_completion():
    """is_complete()==false 时，不允许提前 finish()。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m", "1h"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    with pytest.raises(ValueError, match="finish\\(\\) 只能在 planner 完成后调用"):
        planner.finish()


def test_planner_rejects_request_mismatch_during_ingest():
    """ingest_response(...) 只能消费当前挂起请求。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    request = planner.next_request()
    assert request is not None

    with pytest.raises(ValueError, match="当前挂起请求不匹配"):
        planner.ingest_response(
            request.__class__(
                source_key=request.source_key,
                since=request.since + 1,
                limit=request.limit,
            ),
            _ohlcv_df([0, 900_000, 1_800_000]),
        )


@pytest.mark.parametrize(
    ("df", "expected_msg"),
    [
        (
            pl.DataFrame(
                {
                    "open": [1.0, 1.0, 1.0],
                    "high": [1.0, 1.0, 1.0],
                    "low": [1.0, 1.0, 1.0],
                    "close": [1.0, 1.0, 1.0],
                    "volume": [1.0, 1.0, 1.0],
                }
            ),
            "缺少 time 列",
        ),
        (
            pl.DataFrame(
                {
                    "time": [0.0, 900_000.0, 1_800_000.0],
                    "open": [1.0, 1.0, 1.0],
                    "high": [1.0, 1.0, 1.0],
                    "low": [1.0, 1.0, 1.0],
                    "close": [1.0, 1.0, 1.0],
                    "volume": [1.0, 1.0, 1.0],
                }
            ),
            "time 列必须是 Int64",
        ),
        (
            pl.DataFrame(
                {
                    "time": [0, None, 1_800_000],
                    "open": [1.0, 1.0, 1.0],
                    "high": [1.0, 1.0, 1.0],
                    "low": [1.0, 1.0, 1.0],
                    "close": [1.0, 1.0, 1.0],
                    "volume": [1.0, 1.0, 1.0],
                }
            ),
            "time 列存在 null",
        ),
        (
            pl.DataFrame(
                {
                    "time": [0, 900_000, 900_000],
                    "open": [1.0, 1.0, 1.0],
                    "high": [1.0, 1.0, 1.0],
                    "low": [1.0, 1.0, 1.0],
                    "close": [1.0, 1.0, 1.0],
                    "volume": [1.0, 1.0, 1.0],
                }
            ),
            "time 列必须严格递增",
        ),
    ],
)
def test_planner_rejects_structurally_invalid_response_df(
    df: pl.DataFrame,
    expected_msg: str,
):
    """response 结构非法时必须在 ingest_response(...) 阶段直接报错。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    request = planner.next_request()
    assert request is not None

    with pytest.raises(ValueError, match=expected_msg):
        planner.ingest_response(request, df)


def test_planner_nonzero_warmup_converges_on_effective_anchor():
    """required_warmup > 0 时，planner 必须围绕 effective_since 收敛，而不是无限左扩。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            indicators_params={"ohlcv_15m": {"sma_0": {"period": Param(5)}}},
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    first_request = planner.next_request()
    assert first_request is not None
    assert first_request.since == 0
    assert first_request.limit == 3
    planner.ingest_response(first_request, _ohlcv_df([0, 900_000, 1_800_000]))

    second_request = planner.next_request()
    assert second_request is not None
    assert second_request.source_key == "ohlcv_15m"
    assert second_request.since == -9_000_000
    assert second_request.limit == 13
    planner.ingest_response(
        second_request,
        _ohlcv_df(
            [
                -9_000_000,
                -8_100_000,
                -7_200_000,
                -6_300_000,
                -5_400_000,
                -4_500_000,
                -3_600_000,
                -2_700_000,
                -1_800_000,
                -900_000,
                0,
                900_000,
                1_800_000,
            ]
        ),
    )

    assert planner.is_complete() is True
    assert planner.next_request() is None

    data_pack = planner.finish()
    assert data_pack.ranges["ohlcv_15m"].warmup_bars == 4
    assert data_pack.ranges["ohlcv_15m"].active_bars == 3
    assert data_pack.source["ohlcv_15m"]["time"].to_list() == [
        -3_600_000,
        -2_700_000,
        -1_800_000,
        -900_000,
        0,
        900_000,
        1_800_000,
    ]


def test_planner_uses_first_returned_base_bar_as_live_anchor():
    """base 首根有效 bar 晚于 since 时，planner 必须锚定真实返回首根。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=1,
            effective_limit=3,
            indicators_params={"ohlcv_15m": {"sma_0": {"period": Param(3)}}},
            backtest_params=_backtest_without_exec_warmup(),
        )
    )

    first_request = planner.next_request()
    assert first_request is not None
    planner.ingest_response(first_request, _ohlcv_df([10, 900_010, 1_800_010]))

    second_request = planner.next_request()
    assert second_request is not None
    planner.ingest_response(
        second_request,
        _ohlcv_df(
            [
                -1_799_990,
                -899_990,
                10,
                900_010,
                1_800_010,
            ]
        ),
    )

    assert planner.is_complete() is True
    data_pack = planner.finish()
    assert data_pack.ranges["ohlcv_15m"].warmup_bars == 2
    assert data_pack.source["ohlcv_15m"]["time"].to_list() == [
        -1_799_990,
        -899_990,
        10,
        900_010,
        1_800_010,
    ]


def test_planner_exec_warmup_uses_param_max_when_optimized():
    """planner 必须直接消费共享 helper 的 optimize=true -> Param.max 口径。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=3,
            backtest_params=BacktestParams(
                initial_capital=10_000.0,
                fee_fixed=0.0,
                fee_pct=0.0,
                sl_atr=Param(2.0),
                atr_period=Param(value=5.0, min=5.0, max=11.0, optimize=True),
                sl_exit_in_bar=False,
                tp_exit_in_bar=False,
                sl_trigger_mode=False,
                tp_trigger_mode=False,
                tsl_trigger_mode=False,
                sl_anchor_mode=False,
                tp_anchor_mode=False,
                tsl_anchor_mode=False,
                sl_pct=None,
                tp_pct=None,
                tsl_pct=None,
                tp_atr=None,
                tsl_atr=None,
            ),
        )
    )

    assert planner.required_warmup_by_key["ohlcv_15m"] == 11


def test_planner_non_base_source_advances_through_tail_head_time_and_warmup():
    """非 base source 必须按 TailCoverage -> HeadTimeCoverage -> HeadWarmup 顺序补拉。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m", "1h"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=8,
            indicators_params={
                "ohlcv_15m": {"sma_base": {"period": Param(5)}},
                "ohlcv_1h": {"sma_high": {"period": Param(4)}},
            },
            backtest_params=_backtest_without_exec_warmup(),
            min_request_bars=1,
        )
    )

    base_request_1 = planner.next_request()
    assert base_request_1 is not None
    assert base_request_1.source_key == "ohlcv_15m"
    assert base_request_1.since == 0
    assert base_request_1.limit == 8
    planner.ingest_response(base_request_1, _ohlcv_df(_times(0, 900_000, 8)))

    base_request_2 = planner.next_request()
    assert base_request_2 is not None
    assert base_request_2.source_key == "ohlcv_15m"
    assert base_request_2.since == -3_600_000
    assert base_request_2.limit == 12
    planner.ingest_response(base_request_2, _ohlcv_df(_times(-3_600_000, 900_000, 12)))

    source_request_1 = planner.next_request()
    assert source_request_1 is not None
    assert source_request_1.source_key == "ohlcv_1h"
    assert source_request_1.since == -3_600_000
    assert source_request_1.limit == 4
    planner.ingest_response(source_request_1, _ohlcv_df([-3_600_000, 0]))

    source_request_2 = planner.next_request()
    assert source_request_2 is not None
    assert source_request_2.source_key == "ohlcv_1h"
    assert source_request_2.since == -3_600_000
    assert source_request_2.limit == 5
    planner.ingest_response(source_request_2, _ohlcv_df([0, 3_600_000, 7_200_000]))

    source_request_3 = planner.next_request()
    assert source_request_3 is not None
    assert source_request_3.source_key == "ohlcv_1h"
    assert source_request_3.since == -7_200_000
    assert source_request_3.limit == 6
    planner.ingest_response(
        source_request_3,
        _ohlcv_df([-7_200_000, -3_600_000, 0, 3_600_000, 7_200_000]),
    )

    source_request_4 = planner.next_request()
    assert source_request_4 is not None
    assert source_request_4.source_key == "ohlcv_1h"
    assert source_request_4.since == -10_800_000
    assert source_request_4.limit == 7
    planner.ingest_response(
        source_request_4,
        _ohlcv_df([-10_800_000, -7_200_000, -3_600_000, 0, 3_600_000, 7_200_000]),
    )

    assert planner.is_complete() is True
    assert planner.next_request() is None

    data_pack = planner.finish()
    assert data_pack.ranges["ohlcv_15m"].warmup_bars == 4
    assert data_pack.ranges["ohlcv_1h"].warmup_bars == 3
    assert data_pack.source["ohlcv_1h"]["time"].to_list() == [
        -10_800_000,
        -7_200_000,
        -3_600_000,
        0,
        3_600_000,
        7_200_000,
    ]


def test_planner_fails_fast_when_source_exceeds_max_rounds():
    """补拉轮次达到上限后仍覆盖不足时，planner 必须直接报错。"""
    planner = DataPackFetchPlanner(
        DataPackFetchPlannerInput(
            timeframes=["15m", "1h"],
            base_data_key="ohlcv_15m",
            effective_since=0,
            effective_limit=10,
            backtest_params=_backtest_without_exec_warmup(),
            min_request_bars=1,
            max_rounds_per_source=1,
        )
    )

    base_request = planner.next_request()
    assert base_request is not None
    planner.ingest_response(base_request, _ohlcv_df(_times(0, 900_000, 10)))

    source_request_1 = planner.next_request()
    assert source_request_1 is not None
    assert source_request_1.source_key == "ohlcv_1h"
    assert source_request_1.since == 0
    assert source_request_1.limit == 4
    planner.ingest_response(source_request_1, _ohlcv_df([0, 3_600_000]))

    source_request_2 = planner.next_request()
    assert source_request_2 is not None
    assert source_request_2.source_key == "ohlcv_1h"
    assert source_request_2.since == 0
    assert source_request_2.limit == 5

    with pytest.raises(ValueError, match="补拉轮次超过上限 1"):
        planner.ingest_response(source_request_2, _ohlcv_df([0, 3_600_000]))
