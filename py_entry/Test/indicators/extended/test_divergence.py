import pytest
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from py_entry.Test.indicators.conftest import run_indicator_backtest


def numpy_divergence_logic(prices, indicators, window, idx_gap, recency, is_high=True):
    """
    用 NumPy 实现的背离检测逻辑参考实现。
    完全对齐 Rust 中 divergence.rs 的逻辑。
    """
    # 构造滑动窗口视图
    p_win = sliding_window_view(prices, window)
    i_win = sliding_window_view(indicators, window)

    # 检查 NaN
    has_nan = np.any(np.isnan(p_win), axis=1) | np.any(np.isnan(i_win), axis=1)

    # 找极值相对索引
    if is_high:
        p_peaks = np.argmax(p_win, axis=1)
        i_peaks = np.argmax(i_win, axis=1)
    else:
        # 对底背离求最小值
        p_peaks = np.argmin(p_win, axis=1)
        i_peaks = np.argmin(i_win, axis=1)

    # 判定逻辑
    # recency: 极值点距离窗口右侧(当前K线)的距离
    recency_ok = (window - 1 - p_peaks) < recency
    # gap: 价格峰值必须晚于指标峰值，且间距足够
    gap_val = p_peaks - i_peaks
    div_ok = (p_peaks > i_peaks) & (gap_val >= idx_gap)

    # 组装结果
    res_core = (recency_ok & div_ok & ~has_nan).astype(np.float64)

    # 头部补零
    return np.concatenate([np.zeros(window - 1), res_core])


def test_divergence_logic_alignment(data_dict):
    """
    逻辑对齐测试：验证 Rust 计算出的背离信号与 NumPy 矢量化实现的参考值完全一致。
    """
    window = 10
    idx_gap = 3
    recency = 3

    indicator_configs = {
        "ohlcv_15m": {
            "rsi-divergence_test": {
                "period": {"value": 14},
                "window": {"value": window},
                "mode": {"value": 0.0},  # 顶背离
                "idx_gap": {"value": idx_gap},
                "recency": {"value": recency},
            },
            "cci-divergence_test": {
                "period": {"value": 14},
                "window": {"value": window},
                "mode": {"value": 1.0},  # 底背离
                "idx_gap": {"value": idx_gap},
                "recency": {"value": recency},
            },
        }
    }

    results, data_container = run_indicator_backtest(data_dict, indicator_configs)
    indicators_results = results[0].indicators
    assert indicators_results is not None, "indicators results 不能为空"
    indicators_df = indicators_results["ohlcv_15m"]
    ohlcv_df = data_container.source["ohlcv_15m"]

    # 1. 验证 RSI 顶背离
    rust_rsi_val = (
        indicators_df.select("rsi-divergence_test_rsi").to_series().to_numpy()
    )
    rust_rsi_div = (
        indicators_df.select("rsi-divergence_test_div").to_series().to_numpy()
    )
    price_high = ohlcv_df.select("high").to_series().to_numpy()

    py_rsi_div = numpy_divergence_logic(
        price_high, rust_rsi_val, window, idx_gap, recency, is_high=True
    )

    # 断言完全对齐
    np.testing.assert_allclose(rust_rsi_div, py_rsi_div, err_msg="RSI 顶背离逻辑不一致")

    # 2. 验证 CCI 底背离
    rust_cci_val = (
        indicators_df.select("cci-divergence_test_cci").to_series().to_numpy()
    )
    rust_cci_div = (
        indicators_df.select("cci-divergence_test_div").to_series().to_numpy()
    )
    price_low = ohlcv_df.select("low").to_series().to_numpy()

    py_cci_div = numpy_divergence_logic(
        price_low, rust_cci_val, window, idx_gap, recency, is_high=False
    )

    np.testing.assert_allclose(rust_cci_div, py_cci_div, err_msg="CCI 底背离逻辑不一致")


def test_divergence_column_names(data_dict):
    """
    测试背离指标生成的列名是否符合规划
    """
    indicator_configs = {
        "ohlcv_15m": {
            "cci-divergence_0": {
                "period": {"value": 14},
                "window": {"value": 10},
                "mode": {"value": 0.0},
            },
            "rsi-divergence_debug": {
                "period": {"value": 14},
                "window": {"value": 10},
                "mode": {"value": 0.0},
            },
            "macd-divergence_fast": {
                "fast_period": {"value": 12},
                "slow_period": {"value": 26},
                "signal_period": {"value": 9},
                "window": {"value": 10},
                "mode": {"value": 0.0},
            },
        }
    }

    results, _ = run_indicator_backtest(data_dict, indicator_configs)
    indicators_results = results[0].indicators
    assert indicators_results is not None, "indicators results 不能为空"
    indicators_df = indicators_results["ohlcv_15m"]
    actual_cols = indicators_df.columns

    assert "cci-divergence_0_div" in actual_cols
    assert "cci-divergence_0_cci" in actual_cols
    assert "rsi-divergence_debug_div" in actual_cols
    assert "rsi-divergence_debug_rsi" in actual_cols
    assert "macd-divergence_fast_div" in actual_cols
    assert "macd-divergence_fast_macd" in actual_cols
