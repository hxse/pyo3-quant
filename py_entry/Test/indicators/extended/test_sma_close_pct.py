import pytest
from py_entry.Test.indicators.conftest import run_indicator_backtest
from py_entry.types import Param


def test_sma_close_pct_column_names(data_dict):
    """
    测试 SMA-Close-PCT 指标生成的列名是否符合规划 (indicators_name_rule.md)
    规则: 单输出指标, 列名应与 Key 一致
    """
    indicator_configs = {
        "ohlcv_15m": {
            "sma-close-pct_0": {"period": Param(20)},
            "sma-close-pct_fast": {"period": Param(5)},
        }
    }

    results, _ = run_indicator_backtest(data_dict, indicator_configs)

    # 获取指标结果集
    indicators_results = results[0].indicators
    assert indicators_results is not None, "indicators results 不能为空"
    indicators_df = indicators_results["ohlcv_15m"]
    actual_cols = indicators_df.columns

    print(f"\nActual columns: {actual_cols}")

    # 验证单输出列名是否与 key 完全一致
    assert "sma-close-pct_0" in actual_cols
    assert "sma-close-pct_fast" in actual_cols

    # 验证数据是否存在 (非全空)
    assert indicators_df.select("sma-close-pct_0").to_series().null_count() < len(
        indicators_df
    )
