import pytest
import polars as pl

# 从 example.py 导入自定义 Builder 类
from .example import (
    BacktestRunner,
    CustomParamBuilder,
    CustomSignalTemplateBuilder,
    CustomEngineSettingsBuilder,
)


@pytest.fixture(scope="class")
def backtest_result():
    """缓存回测结果，避免重复运行"""
    br = BacktestRunner()

    result = (
        br.with_data(
            {
                "timeframes": ["15m", "1h", "4h"],
                "start_time": 1735689600000,
                "num_bars": 10000,
                "fixed_seed": True,
            }
        )
        .with_param_set(param_builder=CustomParamBuilder())
        .with_templates(signal_template_builder=CustomSignalTemplateBuilder())
        .with_engine_settings(engine_settings_builder=CustomEngineSettingsBuilder())
        .run()
    )

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
