"""
demo_sma_crossover 的配置文件

此测试用例使用硬编码的 OHLCV 数据和预期输出，验证回测引擎的正确性。

策略：双均线交叉
- 快线：SMA(5)
- 慢线：SMA(10)
- 进场：金叉做多，死叉做空
- 离场：反向交叉
"""

import pytest
import polars as pl
from pathlib import Path

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.data_generator.config import DirectDataConfig
from py_entry.data_conversion.types import (
    BacktestParams,
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
    SettingContainer,
    ExecutionStage,
)


@pytest.fixture(scope="module")
def demo_dir():
    """返回当前demo目录的路径"""
    return Path(__file__).parent


@pytest.fixture(scope="module")
def ohlcv_15m(demo_dir):
    """加载硬编码的 OHLCV 数据"""
    csv_path = demo_dir / "ohlcv_15m.csv"
    return pl.read_csv(csv_path)


@pytest.fixture(scope="module")
def expected_output(demo_dir, backtest_result):
    """
    加载预期输出数据。
    如果文件不存在，则从当前回测结果自动生成，并报错提示用户审查。
    """
    csv_path = demo_dir / "expected_output.csv"

    if not csv_path.exists():
        # 从回测结果中提取 DataFrame
        if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
            pytest.fail("无法生成预期输出：回测结果为空")

        df = backtest_result[0].backtest_result
        df.write_csv(csv_path)

        pytest.fail(
            f"预期输出文件不存在: {csv_path}\n"
            "已根据当前回测结果自动生成该文件。\n"
            "请务必人工审查生成的 CSV 文件内容，确认其作为黄金标准（Golden Master）的正确性。\n"
            "确认无误后，再次运行测试即可通过。"
        )

    # 加载并进行特殊处理：CSV 无法保留 Int8 类型，推断为 i64，此处强制转回以通过 strict 比较
    df = pl.read_csv(csv_path)
    if "risk_in_bar_direction" in df.columns:
        df = df.with_columns(pl.col("risk_in_bar_direction").cast(pl.Int8))
    return df


@pytest.fixture(scope="module")
def backtest_result(ohlcv_15m):
    """执行回测并返回结果"""
    br = BacktestRunner()

    # 使用 DirectDataConfig 传递硬编码数据
    data_config = DirectDataConfig(
        data={"ohlcv_15m": ohlcv_15m}, BaseDataKey="ohlcv_15m"
    )

    # 配置指标参数：SMA(5) 和 SMA(10)
    indicators_params: IndicatorsParams = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(5)},
            "sma_slow": {"period": Param.create(10)},
        },
    }

    # 信号参数：无自定义参数
    signal_params: SignalParams = {}

    # 回测参数：无风控
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0.0,
        fee_pct=0.001,  # 0.1%手续费
        pause_drawdown=Param.create(0, 0, 0, 0),
        pause_sma=Param.create(0, 0, 0, 0),
        pause_ema=Param.create(0, 0, 0, 0),
        exit_in_bar=False,
        exit_in_bar_fallback=False,
        tsl_per_bar_update=False,
        sl_pct=Param.create(0, 0, 0, 0),  # 禁用
        tp_pct=Param.create(0, 0, 0, 0),  # 禁用
        tsl_pct=Param.create(0, 0, 0, 0),  # 禁用
        sl_atr=Param.create(0, 0, 0, 0),  # 禁用
        tp_atr=Param.create(0, 0, 0, 0),  # 禁用
        tsl_atr=Param.create(0, 0, 0, 0),  # 禁用
        atr_period=Param.create(14, 7, 21, 1),
    )

    # 信号模板：双均线交叉策略
    # 金叉进多：快线上穿慢线
    enter_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0",
        ],
    )

    # 死叉进空：快线下穿慢线
    enter_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 x< sma_slow, ohlcv_15m, 0",
        ],
    )

    # 多头离场：快线下穿慢线
    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 x< sma_slow, ohlcv_15m, 0",
        ],
    )

    # 空头离场：快线上穿慢线
    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0",
        ],
    )

    signal_template = SignalTemplate(
        name="sma_crossover_strategy",
        enter_long=enter_long_group,
        enter_short=enter_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
    )

    # 引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.BACKTEST,
        return_only_final=False,
    )

    # 执行回测
    br.setup(
        data_source=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    br.run()

    return br.results


@pytest.fixture
def backtest_df(backtest_result):
    """从回测结果中提取DataFrame"""
    if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
        return None
    return backtest_result[0].backtest_result
