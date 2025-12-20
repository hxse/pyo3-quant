import pytest

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.data_generator import (
    DataGenerationParams,
)
from py_entry.data_conversion.types import (
    BacktestParams,
    IndicatorsParams,
    Param,
    PerformanceParams,
    LogicOp,
    SignalGroup,
    SignalParams,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
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
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )

    # 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param.create(5),
            },
            "sma_slow": {
                "period": Param.create(10),
            },
        },
    }

    # 自定义信号参数
    signal_params = {}

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
        sl_pct=Param.create(2, 0.5, 5, 0.1),
        tp_pct=Param.create(2, 0.5, 5, 0.1),
        tsl_pct=Param.create(1, 0.5, 3, 0.1),
        sl_atr=Param.create(2, 1, 5, 0.5),
        tp_atr=Param.create(3, 1, 5, 0.5),
        tsl_atr=Param.create(2, 1, 4, 0.5),
        atr_period=Param.create(14, 7, 21, 1),
    )

    # 自定义信号模板
    # 双均线策略：金叉进多，死叉进空
    enter_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0",
        ],
    )

    enter_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0",
        ],
    )

    # 离场条件：反向交叉
    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0",
        ],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0",
        ],
    )

    signal_template = SignalTemplate(
        enter_long=enter_long_group,
        enter_short=enter_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
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
    br.run()

    return br.results


@pytest.fixture
def backtest_df(backtest_result):
    """从回测结果中提取DataFrame"""
    if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
        return None
    return backtest_result[0].backtest_result


@pytest.fixture
def required_fixed_cols():
    """固定列定义（基于新的价格驱动架构）"""
    return [
        # 价格状态列
        "entry_long_price",
        "entry_short_price",
        "exit_long_price",
        "exit_short_price",
        # Risk 状态列 (新架构)
        "risk_exit_long_price",
        "risk_exit_short_price",
        "risk_in_bar_direction",  # i8 类型 (0, 1, -1)
        # 资金状态列
        "balance",
        "equity",
        "current_drawdown",
        "trade_pnl_pct",
        "total_return_pct",
        "fee",
        "fee_cum",
    ]


@pytest.fixture
def optional_cols():
    """可选列定义（基于output.rs源代码）"""
    return {
        "sl_pct_price_long": "百分比止损价格(多)",
        "sl_pct_price_short": "百分比止损价格(空)",
        "tp_pct_price_long": "百分比止盈价格(多)",
        "tp_pct_price_short": "百分比止盈价格(空)",
        "tsl_pct_price_long": "百分比跟踪止损价格(多)",
        "tsl_pct_price_short": "百分比跟踪止损价格(空)",
        "atr": "ATR指标值",
        "sl_atr_price_long": "ATR止损价格(多)",
        "sl_atr_price_short": "ATR止损价格(空)",
        "tp_atr_price_long": "ATR止盈价格(多)",
        "tp_atr_price_short": "ATR止盈价格(空)",
        "tsl_atr_price_long": "ATR跟踪止损价格(多)",
        "tsl_atr_price_short": "ATR跟踪止损价格(空)",
    }


@pytest.fixture
def financial_cols():
    """财务相关列定义"""
    return [
        "balance",
        "equity",
        "current_drawdown",
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
