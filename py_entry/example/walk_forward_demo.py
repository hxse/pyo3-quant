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
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig
from py_entry.constants import GLOBAL_SEED


def get_walk_forward_demo_config() -> StrategyConfig:
    """获取 walk_forward_demo 示例的完整策略配置。"""
    cfg = get_strategy("mtf_bbands_rsi_sma")
    if not isinstance(cfg.data_config, DataGenerationParams):
        raise TypeError("mtf_bbands_rsi_sma.data_config 必须为 DataGenerationParams")

    # 1. 模拟数据配置 (较长的数据以支持滚动)
    simulated_data_config = cfg.data_config.model_copy(
        update={
            "timeframes": ["15m"],
            "start_time": get_utc_timestamp_ms("2025-01-01 00:00:00"),
            "num_bars": 10000,  # 增加数据量
            "fixed_seed": GLOBAL_SEED,
            "base_data_key": "ohlcv_15m",
        }
    )

    # 2. 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param(
                    20,
                    min=10,
                    max=40,
                    step=5.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                ),
            },
            "sma_slow": {
                "period": Param(
                    100,
                    min=60,
                    max=200,
                    step=10.0,
                    optimize=True,
                    dtype=ParamType.Integer,
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
        sl_pct=Param(0.01, min=0.005, max=0.05, optimize=True),
        tp_pct=Param(0.02, min=0.005, max=0.08, optimize=True),
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
        execution_stage=ExecutionStage.Performance,
        return_only_final=True,
    )

    return StrategyConfig(
        name="walk_forward_demo",
        description="Walk Forward 优化示例",
        data_config=simulated_data_config,
        indicators_params=indicators_params,
        signal_params={},
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        performance_params=performance_params,
    )


def get_walk_forward_config() -> WalkForwardConfig:
    """获取 Walk Forward 配置。"""
    opt_config = OptimizerConfig(
        max_samples=200,
        samples_per_round=50,
        stop_patience=3,
        min_samples=50,
        max_rounds=10,
        seed=GLOBAL_SEED,
    )
    return WalkForwardConfig(
        train_ratio=0.5,
        transition_ratio=0.1,
        test_ratio=0.25,
        inherit_prior=True,
        optimizer_config=opt_config,
    )


def run_walk_forward_demo(
    *,
    config: StrategyConfig | None = None,
    walk_forward_config: WalkForwardConfig | None = None,
) -> dict[str, object]:
    """运行 Walk Forward 演示，返回摘要结果供 notebook 或脚本调用。"""
    logger.info("启动向前滚动优化 (Walk Forward) 演示...")
    cfg = config if config is not None else get_walk_forward_demo_config()

    # 7. 配置 Backtest
    bt = Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        backtest=cfg.backtest_params,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
        signal=cfg.signal_params,
    )

    # 8. 配置 Walk Forward
    wf_config = (
        walk_forward_config
        if walk_forward_config is not None
        else get_walk_forward_config()
    )

    logger.info("开始执行 Walk Forward Optimization...")
    start_time = time.time()

    wf_result = bt.walk_forward(wf_config)

    elapsed = time.time() - start_time
    logger.info(f"Walk Forward 完成，总耗时: {elapsed:.2f}秒")

    print("\n================= Walk Forward 结果 =================")
    agg_metrics = wf_result.aggregate_test_metrics
    print(f"\nStitched CalmarRaw: {agg_metrics.get('calmar_ratio_raw', 0.0):.4f}")
    optimize_metric_text = str(wf_result.optimize_metric)
    print(f"Optimization Metric: {optimize_metric_text}")
    print(f"Window Count: {len(wf_result.raw.window_results)}")
    print(f"Stitched Time Range: {wf_result.stitched_result.time_range}")
    print(f"Rolling Every Days: {wf_result.stitched_result.rolling_every_days:.4f}")
    print("-----------------------------------------------------")
    for w in wf_result.raw.window_results:
        metrics = w.summary.performance or {}
        print(f"Window {w.window_id}:")
        print(
            "  Range: "
            f"Train={w.train_range}, "
            f"Transition={w.transition_range}, "
            f"Test={w.test_range}"
        )
        print(f"  Has Cross Boundary Position: {w.has_cross_boundary_position}")
        print(f"  Test CalmarRaw: {metrics.get('calmar_ratio_raw', 0.0):.4f}")
        print(f"  Best Params:  {w.best_params}")
    print("=====================================================")

    # 返回结构化摘要，便于 notebook 与 __main__ 复用。
    return {
        "elapsed_seconds": elapsed,
        "optimize_metric": optimize_metric_text,
        "stitched_calmar_raw": agg_metrics.get("calmar_ratio_raw", 0.0),
        "window_count": len(wf_result.raw.window_results),
    }


def format_result_for_ai(summary: dict[str, object]) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== WALK_FORWARD_DEMO_RESULT ===")
    lines.append(
        f"elapsed_seconds={summary.get('elapsed_seconds')}, "
        f"window_count={summary.get('window_count')}"
    )
    lines.append(
        f"optimize_metric={summary.get('optimize_metric')}, "
        f"stitched_calmar_raw={summary.get('stitched_calmar_raw')}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    run_summary = run_walk_forward_demo()
    print(format_result_for_ai(run_summary))
