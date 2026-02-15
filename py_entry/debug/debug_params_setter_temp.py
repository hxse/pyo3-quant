from pyo3_quant._pyo3_quant import Param
from pyo3_quant._pyo3_quant import ParamType
from pyo3_quant._pyo3_quant import PerformanceMetric
from pyo3_quant._pyo3_quant import SingleParamSet


def main() -> None:
    """临时调试脚本：验证业务层 setter 是否按预期生效。"""
    params = SingleParamSet()

    # 1) indicators: 直接按业务键路径写入
    params.set_indicator_param(
        "ohlcv_15m",
        "sma",
        "period",
        Param(
            20.0,
            min=2.0,
            max=200.0,
            dtype=ParamType.Integer,
            optimize=True,
            step=1.0,
        ),
    )
    assert params.indicators["ohlcv_15m"]["sma"]["period"].value == 20.0

    # 2) signal: 单参数写入
    params.set_signal_param("rsi_lower", Param(30.0))
    assert params.signal["rsi_lower"].value == 30.0

    # 3) backtest: 三类参数分别写入
    params.set_backtest_optimizable_param("sl_pct", Param(0.02))
    assert params.backtest.sl_pct is not None
    assert params.backtest.sl_pct.value == 0.02

    params.set_backtest_bool_param("sl_exit_in_bar", False)
    assert params.backtest.sl_exit_in_bar is False

    params.set_backtest_f64_param("initial_capital", 20_000.0)
    assert params.backtest.initial_capital == 20_000.0

    # 4) performance: 业务 setter 写入
    params.set_performance_metrics([PerformanceMetric.CalmarRatioRaw])
    assert params.performance.metrics == [PerformanceMetric.CalmarRatioRaw]

    params.set_performance_risk_free_rate(0.03)
    assert params.performance.risk_free_rate == 0.03

    params.set_performance_leverage_safety_factor(1.5)
    assert params.performance.leverage_safety_factor == 1.5

    # 5) 错误路径: 未知字段应抛 ValueError
    try:
        params.set_backtest_f64_param("unknown_field", 1.0)
        raise AssertionError("expected ValueError for unknown backtest field")
    except ValueError:
        pass

    print("debug_params_setter_temp: PASS")


if __name__ == "__main__":
    main()
