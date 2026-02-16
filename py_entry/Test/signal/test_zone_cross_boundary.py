import polars as pl
from datetime import datetime, timedelta

from py_entry.data_generator import DirectDataConfig
from py_entry.types import (
    ExecutionStage,
    SignalGroup,
    LogicOp,
    SignalTemplate,
    Param,
)
from py_entry.Test.shared import make_backtest_runner, make_engine_settings


def test_zone_cross_boundary_inclusive():
    """
    测试 x>= (inclusive) 在边界条件下的行为。
    使用 DirectDataConfig 注入精确数据。

    测试序列 (close):
    [20, 29, 30, 30, 30, 50, 70, 71, 50]

    指标: close (直接使用 close 价格作为指标)
    信号: close x>= 30..70

    预期行为:
    idx 0 (20): False
    idx 1 (29): False
    idx 2 (30): True (Trigger: prev=29 < 30, curr=30 >= 30)
    idx 3 (30): True (Active: prev=30 !< 30 NO TRIGGER, but in zone [30, 70])
    idx 4 (30): True (Active)
    idx 5 (50): True (Active)
    idx 6 (70): True (Active: upper boundary is included)
    idx 7 (71): False (Deactivate: val > 70)
    idx 8 (50): False (Need re-trigger)
    """

    # 1. 构造精确的 OHLCV 数据
    # 为了满足指标计算长度（如 ATR 14），我们在前面填充一些默认数据
    padding_len = 20
    prefix_closes = [20.0] * padding_len

    # 关键测试序列
    test_closes = [20.0, 29.0, 30.0, 30.0, 30.0, 50.0, 70.0, 71.0, 50.0]
    closes = prefix_closes + test_closes
    num_bars = len(closes)

    # 生成时间序列
    start_time = datetime(2024, 1, 1)
    times = [
        int((start_time + timedelta(minutes=15 * i)).timestamp() * 1000)
        for i in range(num_bars)
    ]

    df = pl.DataFrame(
        {
            "time": times,
            "open": closes,  # close=open for simplicity
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000.0] * num_bars,
        }
    )

    # 添加 path pattern 所需的 date 列 (虽然 DirectDataConfig 可能不强制需要，但保持一致性)
    df = df.with_columns(
        pl.from_epoch(pl.col("time"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
        .alias("date")
    )

    # 2. 配置数据源
    data_config = DirectDataConfig(data={"ohlcv_15m": df}, base_data_key="ohlcv_15m")

    # 3. 配置信号
    # Signal: close x>= 30..70
    # 注意：我们直接用 ohlcv_15m 的 close 列作为指标，无需计算 RSI
    # 但 Backtest 需要 indicators 参数，我们可以配置一个 dummy indicator 或者直接引用 close
    # 这里我们定义一个简单的 sma_1 (period=1) 其实就是 close

    # 为了简单，我们直接在 signal 模板中引用 ohlcv_15m 的 close 列
    # 语法支持: data_key, column_name
    # close 在 ohlcv_15m 中，可以直接用 ohlcv_15m.close 或者简写 (如果支持)
    # 这里的 parser 支持 "stream_name" 作为操作数
    # 但通常是 "indicator_name"
    # 我们配置一个 SMA(1) 来代表 Close

    indicators_params = {"ohlcv_15m": {"sma_1": {"period": Param(1)}}}

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_1 x>= 30..70"],  # sma_1 is effectively close price
        )
    )

    # 4. 运行回测
    runner = make_backtest_runner(
        data_source=data_config,
        indicators=indicators_params,
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )

    result = runner.run()

    # 5. 验证结果
    assert result.summary is not None
    signals = result.summary.signals
    assert signals is not None

    entry_long = signals["entry_long"].to_list()

    # 取出最后几根实际上对应测试序列的结果
    result_slice = entry_long[-len(test_closes) :]

    expected = [
        False,  # 20
        False,  # 29
        True,  # 30 (Trigger: 29 -> 30)
        True,  # 30 (Active: 30->30)
        True,  # 30 (Active)
        True,  # 50 (Active)
        True,  # 70 (Active: Inclusive Upper)
        False,  # 71 (Disable: > 70)
        False,  # 50 (Wait for re-trigger)
    ]

    for i, (res, exp) in enumerate(zip(result_slice, expected)):
        assert res == exp, (
            f"Mismatch at index {i} (Close={test_closes[i]}): Expected {exp}, Got {res}"
        )


def test_zone_cross_boundary_strict_down():
    """
    测试 x< (strict) 在边界条件下的行为。
    信号: sma_1 x< 70..30
    活跃区间: (30, 70)
    激活条件: prev >= 70 AND curr < 70
    失效条件: val <= 30 OR val >= 70

    测试序列 (close):
    [80, 71, 70, 70, 50, 30, 29, 50]
    """
    padding_len = 20
    prefix_closes = [80.0] * padding_len
    test_closes = [80.0, 71.0, 70.0, 70.0, 50.0, 30.0, 29.0, 50.0]
    closes = prefix_closes + test_closes
    num_bars = len(closes)

    start_time = datetime(2024, 1, 1)
    times = [
        int((start_time + timedelta(minutes=15 * i)).timestamp() * 1000)
        for i in range(num_bars)
    ]

    df = pl.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000.0] * num_bars,
        }
    )
    df = df.with_columns(
        pl.from_epoch(pl.col("time"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
        .alias("date")
    )

    data_config = DirectDataConfig(data={"ohlcv_15m": df}, base_data_key="ohlcv_15m")
    indicators_params = {"ohlcv_15m": {"sma_1": {"period": Param(1)}}}

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_1 x< 70..30"],
        )
    )

    runner = make_backtest_runner(
        data_source=data_config,
        indicators=indicators_params,
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )

    result = runner.run()
    assert result.summary is not None
    signals = result.summary.signals
    assert signals is not None
    entry_long = signals["entry_long"].to_list()[-len(test_closes) :]

    expected = [
        False,  # 80
        False,  # 71
        False,  # 70 (curr < 70 required, 70 is not < 70)
        False,  # 70
        True,  # 50 (Trigger: prev=70 >= 70, curr=50 < 70)
        False,  # 30 (Deactivate: val <= 30, 30 <= 30 is True)
        False,  # 29 (Deactivate)
        False,  # 50 (Wait re-trigger)
    ]

    for i, (res, exp) in enumerate(zip(entry_long, expected)):
        assert res == exp, (
            f"Mismatch at index {i} (Close={test_closes[i]}): Expected {exp}, Got {res}"
        )


def test_zone_cross_boundary_inclusive_down():
    """
    测试 x<= (inclusive) 在边界条件下的行为。
    信号: sma_1 x<= 70..30
    活跃区间: [30, 70]
    激活条件: prev > 70 AND curr <= 70
    失效条件: val < 30 OR val > 70

    测试序列 (close):
    [80, 71, 70, 70, 50, 30, 29, 50]
    """
    padding_len = 20
    prefix_closes = [80.0] * padding_len
    test_closes = [80.0, 71.0, 70.0, 70.0, 50.0, 30.0, 29.0, 50.0]
    closes = prefix_closes + test_closes
    num_bars = len(closes)

    start_time = datetime(2024, 1, 1)
    times = [
        int((start_time + timedelta(minutes=15 * i)).timestamp() * 1000)
        for i in range(num_bars)
    ]

    df = pl.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000.0] * num_bars,
        }
    )
    df = df.with_columns(
        pl.from_epoch(pl.col("time"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
        .alias("date")
    )

    data_config = DirectDataConfig(data={"ohlcv_15m": df}, base_data_key="ohlcv_15m")
    indicators_params = {"ohlcv_15m": {"sma_1": {"period": Param(1)}}}

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_1 x<= 70..30"],
        )
    )

    runner = make_backtest_runner(
        data_source=data_config,
        indicators=indicators_params,
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )

    result = runner.run()
    assert result.summary is not None
    signals = result.summary.signals
    assert signals is not None
    entry_long = signals["entry_long"].to_list()[-len(test_closes) :]

    expected = [
        False,  # 80
        False,  # 71
        True,  # 70 (Trigger: prev=71 > 70, curr=70 <= 70)
        True,  # 70 (Active: in [30, 70])
        True,  # 50 (Active)
        True,  # 30 (Active: in [30, 70])
        False,  # 29 (Deactivate: val < 30)
        False,  # 50 (Wait re-trigger)
    ]

    for i, (res, exp) in enumerate(zip(entry_long, expected)):
        assert res == exp, (
            f"Mismatch at index {i} (Close={test_closes[i]}): Expected {exp}, Got {res}"
        )


if __name__ == "__main__":
    test_zone_cross_boundary_inclusive()
    test_zone_cross_boundary_strict_down()
    test_zone_cross_boundary_inclusive_down()
