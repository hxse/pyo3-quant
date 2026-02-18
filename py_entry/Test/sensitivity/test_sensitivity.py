import pytest
import numpy as np
from py_entry.types import (
    SensitivityConfig,
    OptimizeMetric,
    Param,
    ExecutionStage,
    SignalTemplate,
    SignalGroup,
    LogicOp,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import (
    make_backtest_params,
    make_backtest_runner,
    make_engine_settings,
)


@pytest.fixture
def sensitivity_setup():
    """Setup a basic backtest instance for testing"""
    # 1. Setup Data Source (Simulated)
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=5000,  # Small number for fast tests
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. Define Params with Optimizable Param
    indicators = {
        "ohlcv_15m": {
            "sma": {"period": Param(value=14, optimize=True, min=5, max=50, step=1)}
        }
    }

    signal_params = {}

    backtest_params = make_backtest_params(fee_fixed=0, fee_pct=0.0005)

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND, comparisons=["close,ohlcv_15m,0 x> sma,ohlcv_15m,0"]
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND, comparisons=["close,ohlcv_15m,0 x< sma,ohlcv_15m,0"]
        ),
    )

    engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Performance, return_only_final=True
    )

    bt = make_backtest_runner(
        data_source=data_config,
        indicators=indicators,
        signal=signal_params,
        backtest=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        enable_timing=False,
    )

    return bt


def test_basic_sensitivity_run(sensitivity_setup):
    """Test basic sensitivity analysis run"""
    bt = sensitivity_setup
    config = SensitivityConfig(jitter_ratio=0.1, n_samples=10, seed=42)

    result = bt.sensitivity(config=config)

    assert result is not None
    assert len(result.samples) == 10
    # Original value might be anything but should be float
    assert isinstance(result.original_value, float)
    assert isinstance(result.mean, float)
    assert isinstance(result.std, float)
    assert isinstance(result.cv, float)
    assert isinstance(result.min, float)
    assert isinstance(result.max, float)


def test_fixed_seed_reproducibility(sensitivity_setup):
    """Test that fixed seed produces identical results"""
    bt = sensitivity_setup
    config = SensitivityConfig(jitter_ratio=0.1, n_samples=5, seed=123)

    result1 = bt.sensitivity(config=config)
    result2 = bt.sensitivity(config=config)

    # Check that sample values are identical
    vals1 = [s.values for s in result1.samples]
    vals2 = [s.values for s in result2.samples]

    assert vals1 == vals2
    assert result1.mean == result2.mean
    assert result1.std == result2.std


def test_different_seeds_different_results(sensitivity_setup):
    """Test that different seeds produce different results"""
    bt = sensitivity_setup
    config1 = SensitivityConfig(jitter_ratio=0.1, n_samples=5, seed=123)
    config2 = SensitivityConfig(jitter_ratio=0.1, n_samples=5, seed=456)

    result1 = bt.sensitivity(config=config1)
    result2 = bt.sensitivity(config=config2)

    # Check that sample values are DIFFERENT
    vals1 = [s.values for s in result1.samples]
    vals2 = [s.values for s in result2.samples]

    assert vals1 != vals2


def test_no_optimizable_params(sensitivity_setup):
    """Test that error is raised when no params are optimizable"""
    # Create backtest with NO optimizable params
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=100,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    indicators = {
        "ohlcv_15m": {
            "sma": {
                "period": Param(value=14, optimize=False)  # optimize=False
            }
        }
    }

    bt = make_backtest_runner(
        data_source=data_config,
        indicators=indicators,
        signal={},
        backtest=make_backtest_params(initial_capital=10000, fee_fixed=0, fee_pct=0),
        signal_template=SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=[]),
            entry_short=SignalGroup(logic=LogicOp.AND, comparisons=[]),
        ),
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )

    config = SensitivityConfig(n_samples=5)

    with pytest.raises(Exception) as excinfo:
        bt.sensitivity(config=config)

    # Check error message (it comes from Rust: InvalidParam)
    assert "No optimizable parameters found" in str(excinfo.value)


def test_distribution_uniform_vs_normal(sensitivity_setup):
    """Test that different distributions run without error"""
    bt = sensitivity_setup

    config_uni = SensitivityConfig(n_samples=5, distribution="uniform")
    result_uni = bt.sensitivity(config=config_uni)
    assert len(result_uni.samples) == 5

    config_norm = SensitivityConfig(n_samples=5, distribution="normal")
    result_norm = bt.sensitivity(config=config_norm)
    assert len(result_norm.samples) == 5


def test_param_bounds_and_quantization(sensitivity_setup):
    """验证采样值是否严格受限于 min/max 并尊重 step"""
    bt = sensitivity_setup
    # 修改参数，设置明显的边界和步长
    # 由于 PyO3 的 getter 返回的是副本，我们需要读取-修改-写回
    indicators = bt.params.indicators
    # ohlcv_15m -> sma -> period
    p = indicators["ohlcv_15m"]["sma"]["period"]
    p.min = 10
    p.max = 20
    p.step = 5
    p.value = 15
    # 写回
    bt.params.indicators = indicators

    config = SensitivityConfig(jitter_ratio=0.5, n_samples=20, seed=42)
    result = bt.sensitivity(config=config)

    for sample in result.samples:
        val = sample.values[0]
        # 1. 边界检查
        assert 10 <= val <= 20
        # 2. 量化检查 (step=5, value=15, min=10, max=20 -> 只能是 10, 15, 20)
        assert val in [10.0, 15.0, 20.0]


def test_original_value_consistency(sensitivity_setup):
    """验证 sensitivity 结果中的 original_value 是否与常规回测一致"""
    bt = sensitivity_setup
    # 1. 直接回测
    run_result = bt.run()
    # summary.performance 的 key 由 Rust 侧 as_str() 输出，为 snake_case 字符串。
    expected_val = run_result.summary.performance.get("calmar_ratio_raw", 0.0)

    # 2. 敏感性测试
    config = SensitivityConfig(n_samples=5, metric=OptimizeMetric.CalmarRatioRaw)
    result = bt.sensitivity(config=config)

    # 允许微小的浮点误差
    assert pytest.approx(result.original_value) == expected_val


def test_multi_param_jitter(sensitivity_setup):
    """测试多个参数同时参与抖动"""
    bt = sensitivity_setup
    # 增加第二个优化参数：sl_pct (止损比例)
    # 类型匹配 BacktestParams 中的 Optional[Param]
    # PyO3 getter 为副本语义，必须“读取-修改-写回”。
    bp = bt.params.backtest
    bp.sl_pct = Param(value=0.02, optimize=True, min=0.01, max=0.05)
    bt.params.backtest = bp

    config = SensitivityConfig(n_samples=5, seed=42)
    result = bt.sensitivity(config=config)

    for sample in result.samples:
        # 应有两个参数值: [SMA period, sl_pct]
        assert len(sample.values) == 2
    # 验证至少有一个样本的值改变了
    # 原始值组合为 [14.0, 0.02]
    # 注意：由于随机性，个别样本可能恰好等于原始值，因此我们验证"至少有一个不同"而不是"全都不同"
    has_diff = False
    for sample in result.samples:
        if sample.values != [14.0, 0.02]:
            has_diff = True
            break
    assert has_diff, "所有样本都等于原始参数，抖动未生效。"


def test_zero_jitter_error(sensitivity_setup):
    """验证 jitter_ratio=0 时应直接报错 (利用已有的 InvalidParam)"""
    bt = sensitivity_setup
    config = SensitivityConfig(jitter_ratio=0.0, n_samples=5)

    with pytest.raises(Exception) as excinfo:
        bt.sensitivity(config=config)

    assert "jitter_ratio must be greater than 0" in str(excinfo.value)


def test_jitter_magnitude_statistically(sensitivity_setup):
    """统计验证抖动幅度是否符合设置的 jitter_ratio (均匀分布)"""
    bt = sensitivity_setup
    ratio = 0.2
    # 扩大采样数以便于统计验证
    config = SensitivityConfig(
        jitter_ratio=ratio, n_samples=100, distribution="uniform", seed=42
    )
    result = bt.sensitivity(config=config)

    original_val = 14.0
    boundary_min = original_val * (1 - ratio)
    boundary_max = original_val * (1 + ratio)

    vals = [s.values[0] for s in result.samples]

    # 1. 边界检查：由于量化(step=1)，采样值 x 满足：
    # round(original_val * (1-ratio)) <= x <= round(original_val * (1+ratio))
    # 14 * 0.8 = 11.2 -> 11.0
    # 14 * 1.2 = 16.8 -> 17.0
    # 允许由于四舍五入带来的 1 个 step 的偏差
    lower_bound = round(boundary_min)
    upper_bound = round(boundary_max)
    for v in vals:
        assert lower_bound <= v <= upper_bound

    # 2. 统计检查：均值应接近原始值 (大数定律)
    assert pytest.approx(np.mean(vals), rel=0.1) == original_val
