import pytest

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.data_generator import (
    DataGenerationParams,
)
from py_entry.data_conversion.types import (
    BacktestParams,
    CompareOp,
    IndicatorsParams,
    LogicOp,
    Param,
    PerformanceParams,
    SignalGroup,
    SignalParams,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)


@pytest.fixture(scope="class")
def backtest_result():
    """缓存回测结果，避免重复运行"""
    br = BacktestRunner()

    # 创建 DataGenerationParams 对象
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=10000,
        fixed_seed=True,
        BaseDataKey="ohlcv_15m",
    )

    # 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "bbands_0": {
                "period": Param.create(14),
                "std": Param.create(2),
            }
        },
        "ohlcv_1h": {
            "rsi_0": {
                "period": Param.create(14),
            }
        },
        "ohlcv_4h": {
            "sma_0": {
                "period": Param.create(8),
            },
            "sma_1": {
                "period": Param.create(16),
            },
        },
    }

    # 自定义信号参数
    signal_params = {"rsi_midline": Param.create(20, 10, 90, 5)}

    # 自定义回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        pause_drawdown=Param.create(0, 0, 0, 0),
        pause_sma=Param.create(0, 0, 0, 0),
        pause_ema=Param.create(0, 0, 0, 0),
        exit_in_bar=False,
        exit_in_bar_fallback=False,
        tsl_per_bar_update=False,
        sl_pct=Param.create(2, 0.5, 5, 0.1),
        tp_pct=Param.create(2, 0.5, 5, 0.1),
        tsl_pct=Param.create(1, 0.5, 3, 0.1),
        sl_atr=Param.create(2, 1, 5, 0.5),
        tp_atr=Param.create(3, 1, 5, 0.5),
        tsl_atr=Param.create(2, 1, 4, 0.5),
        atr_period=Param.create(14, 7, 21, 1),
    )

    # 自定义信号模板
    enter_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 x> bbands_0_upper, ohlcv_15m, 0",
            "rsi_0, ohlcv_1h, 0 > $rsi_midline",
            "sma_0, ohlcv_4h, 0 > sma_1, ohlcv_4h, 0",
        ],
    )

    signal_template = SignalTemplate(
        name="multi_timeframe_dynamic_strategy", enter_long=enter_long_group
    )

    # 自定义引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )

    # 使用 setup 方法一次性配置所有参数
    br.setup(
        data_source=simulated_data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    # 执行回测
    result = br.run()

    return result


@pytest.fixture
def backtest_df(backtest_result):
    """从回测结果中提取DataFrame"""
    if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
        return None
    return backtest_result[0].backtest_result


@pytest.fixture
def required_fixed_cols():
    """固定列定义（基于output.rs源代码）"""
    return [
        "current_position",
        "balance",
        "equity",
        "peak_equity",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
    ]


@pytest.fixture
def optional_cols():
    """可选列定义（基于output.rs源代码）"""
    return {
        "sl_pct_price": "百分比止损价格",
        "tp_pct_price": "百分比止盈价格",
        "tsl_pct_price": "百分比跟踪止损价格",
        "atr": "ATR指标值",
        "sl_atr_price": "ATR止损价格",
        "tp_atr_price": "ATR止盈价格",
        "tsl_atr_price": "ATR跟踪止损价格",
    }


@pytest.fixture
def valid_positions():
    """有效仓位值集合（基于output.rs注释）"""
    return {0, 1, 2, 3, 4, -1, -2, -3, -4}


@pytest.fixture
def financial_cols():
    """财务相关列定义"""
    return [
        "balance",
        "equity",
        "peak_equity",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
    ]


@pytest.fixture
def price_cols():
    """价格相关列定义"""
    return [
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
    ]


@pytest.fixture
def hold_positions():
    """持有仓位状态值（HoldLong=2, HoldShort=-2）"""
    return [2, -2]
