import time
from loguru import logger
from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    Param,
    PerformanceParams,
    PerformanceMetric,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
    ParamType,
    OptimizerConfig,
    WalkForwardConfig,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def main():
    logger.info("启动向前滚动优化 (Walk Forward) 演示...")

    # 1. 模拟数据配置 (较长的数据以支持滚动)
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=10000,  # 增加数据量
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param.create(
                    20,
                    min=10,
                    max=40,
                    step=5.0,
                    optimize=True,
                    dtype=ParamType.INTEGER,
                ),
            },
            "sma_slow": {
                "period": Param.create(
                    100,
                    min=60,
                    max=200,
                    step=10.0,
                    optimize=True,
                    dtype=ParamType.INTEGER,
                ),
            },
        }
    }

    # 3. 信号逻辑
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "sma_fast,ohlcv_15m,0 x> sma_slow,ohlcv_15m,0",
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "sma_fast,ohlcv_15m,0 x< sma_slow,ohlcv_15m,0",
            ],
        ),
    )

    # 4. 回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1.0,
        fee_pct=0.0005,
        sl_pct=Param.create(0.01, min=0.005, max=0.05, optimize=True),
        tp_pct=Param.create(0.02, min=0.005, max=0.08, optimize=True),
        tsl_pct=None,
        # Default flags required by API
        sl_exit_in_bar=True,
        tp_exit_in_bar=True,
        sl_trigger_mode=True,
        tp_trigger_mode=True,
        tsl_trigger_mode=True,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        tsl_atr_tight=True,
        # Required ATR params (can be None but explicitly set to ensure type safety if needed,
        # or defaults are handled if fields are Optional[Param] but dataclass might not have defaults)
        sl_atr=None,
        tp_atr=None,
        tsl_atr=None,
        atr_period=None,
        # PSAR params
        tsl_psar_af0=None,
        tsl_psar_af_step=None,
        tsl_psar_max_af=None,
    )

    # 5. 性能参数
    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
            PerformanceMetric.CalmarRatio,
        ],
    )

    # 6. 引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=True,
    )

    # 7. 配置 Backtest
    bt = Backtest(
        enable_timing=True,
        data_source=simulated_data_config,
        indicators=indicators_params,
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        signal={},  # Added dummy signal to match Init signature if needed (Backtest init expects signal param if not optional? Wait, check Backtest signature)
        # Backtest init: signal: Optional[SignalParams] = None
        # So it's optional.
        # But setup logic required it?
        # Let's check logic. Backtest(..., signal=None) -> build_signal_params(None) -> returns SignalParams(params={}) (empty).
        # So it works.
    )

    # 8. 配置 Walk Forward
    opt_config = OptimizerConfig(
        max_samples=200,
        samples_per_round=50,
        stop_patience=3,
        min_samples=50,
        max_rounds=10,
    )

    wf_config = WalkForwardConfig(
        train_ratio=0.5,
        test_ratio=0.25,
        step_ratio=0.25,
        inherit_prior=True,
        optimizer_config=opt_config,
    )

    logger.info("开始执行 Walk Forward Optimization...")
    start_time = time.time()

    wf_result = bt.walk_forward(wf_config)

    elapsed = time.time() - start_time
    logger.info(f"Walk Forward 完成，总耗时: {elapsed:.2f}秒")

    print("\n================= Walk Forward 结果 =================")
    print(
        f"\nAvg Test Calmar: {wf_result.aggregate_test_metrics.get('calmar_ratio', 0.0):.4f}"
    )
    print(f"Optimization Metric: {wf_result.optimize_metric.value}")
    print("-----------------------------------------------------")
    for w in wf_result.raw.windows:
        print(f"Window {w.window_id}:")
        print(f"  Range: Train={w.train_range}, Test={w.test_range}")
        print(f"  Train Calmar: {w.train_metrics.get('calmar_ratio', 0.0):.4f}")
        print(f"  Test Calmar:  {w.test_metrics.get('calmar_ratio', 0.0):.4f}")
        print(f"  Best Params:  {w.best_params}")
    print("=====================================================")


if __name__ == "__main__":
    main()
