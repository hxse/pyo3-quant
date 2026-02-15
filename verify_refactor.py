import pytest
from pyo3_quant import (
    ParamType,
    PerformanceMetric,
    ExecutionStage,
    LogicOp,
    BenchmarkFunction,
    BacktestParams,
)
from pyo3_quant.backtest_engine import run_backtest_engine


def test_enum_hash():
    """Verify that enums can be used as dictionary keys"""
    d = {}
    d[ParamType.Float] = "float"
    d[PerformanceMetric.TotalReturn] = "return"
    d[ExecutionStage.Backtest] = "stage"
    d[LogicOp.AND] = "logic"
    d[BenchmarkFunction.Sphere] = "bench"

    assert d[ParamType.Float] == "float"
    assert d[PerformanceMetric.TotalReturn] == "return"
    print("Enum hash verification passed!")


def test_backtest_params_kwargs():
    """Verify BacktestParams raises TypeError on unknown kwargs"""
    try:
        # 使用 eval 触发运行时路径，避免静态检查阶段拦截该调用。
        eval("BacktestParams(unknown_arg=123)")
    except TypeError as e:
        print(f"Caught expected TypeError: {e}")
        err = str(e)
        assert "unexpected keyword argument" in err or "Unknown parameter" in err
    else:
        raise AssertionError("BacktestParams did not raise TypeError for unknown kwarg")


def test_backtest_params_default():
    """Verify default values"""
    bp = BacktestParams()
    # Check if defaults align with Rust
    assert bp.initial_capital == 10000.0, f"Expected 10000.0, got {bp.initial_capital}"
    print("BacktestParams default verification passed!")


if __name__ == "__main__":
    test_enum_hash()
    test_backtest_params_kwargs()
    test_backtest_params_default()
    print("All manual verifications passed!")
