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
    OptunaConfig,
    OptimizeMetric,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig
from py_entry.constants import GLOBAL_SEED

import time


def get_optuna_optimizer_demo_config() -> StrategyConfig:
    """获取 optuna_optimizer_demo 示例的完整策略配置。"""
    cfg = get_strategy("mtf_bbands_rsi_sma")
    if not isinstance(cfg.data_config, DataGenerationParams):
        raise TypeError("mtf_bbands_rsi_sma.data_config 必须为 DataGenerationParams")

    # 1. 模拟数据配置
    simulated_data_config = cfg.data_config.model_copy(
        update={
            "timeframes": ["15m"],
            "start_time": get_utc_timestamp_ms("2025-01-01 00:00:00"),
            "num_bars": 5000,
            "fixed_seed": GLOBAL_SEED,
            "base_data_key": "ohlcv_15m",
        }
    )

    # 2. 构建指标参数 (双均线策略)
    # 相比 optimizer_demo.py，这里演示如何显式配置优化属性
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param(
                    20,
                    min=5,  # 优化下界
                    max=50,  # 优化上界
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                ),
            },
            "sma_slow": {
                "period": Param(
                    60,
                    min=51,
                    max=200,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.Integer,
                ),
            },
        }
    }

    # 3. 自定义信号参数 (无需优化)
    signal_params = {}

    # 4. 自定义回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0,
        fee_pct=0.001,
        sl_exit_in_bar=True,
        tp_exit_in_bar=True,
        sl_trigger_mode=True,
        tp_trigger_mode=True,
        tsl_trigger_mode=True,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        tsl_atr_tight=True,
        sl_atr=Param(2.5, min=1.0, max=5.0, step=0.1, optimize=True),
        tsl_atr=Param(2.0, min=1.0, max=5.0, step=0.1, optimize=True),
        atr_period=Param(14),
    )

    # 5. 性能参数 (包含更多对比指标)
    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
            PerformanceMetric.CalmarRatio,
        ],
    )

    # 6. 信号模板 (双均线交叉)
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

    # 7. 引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.Performance,
        return_only_final=True,
    )

    return StrategyConfig(
        name="optuna_optimizer_demo",
        description="Optuna 参数优化示例",
        data_config=simulated_data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        performance_params=performance_params,
    )


def get_optuna_config() -> OptunaConfig:
    """获取 Optuna 优化参数配置。"""
    return OptunaConfig(
        n_trials=1000,  # 总共尝试 1000 次
        batch_size=50,  # 每批并发 50 个
        metric=OptimizeMetric.CalmarRatioRaw,
        direction="maximize",
        sampler="TPE",  # 使用 TPE 采样器
        seed=GLOBAL_SEED,  # 固定种子以便复现
        show_progress_bar=False,  # 隐藏详细进度条
    )


def run_optuna_optimizer_demo(
    *,
    config: StrategyConfig | None = None,
    optuna_config: OptunaConfig | None = None,
) -> dict[str, object]:
    """运行 Optuna 优化示例，返回摘要结果供 notebook 或脚本调用。"""
    logger.info("启动 Optuna 优化器演示...")
    cfg = config if config is not None else get_optuna_optimizer_demo_config()

    # --- 第一阶段: 基准回测 ---
    logger.info("执行基准回测 (使用初始参数)...")
    bt = Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
    )
    result = bt.run()

    baseline_perf = (
        result.summary.performance
        if result.summary and result.summary.performance
        else {}
    )

    # --- 第二阶段: Optuna 参数优化 ---
    logger.info("启动 Optuna 参数优化 (1000次)...")
    opt_config = optuna_config if optuna_config is not None else get_optuna_config()

    start_time = time.perf_counter()
    opt_result = bt.optimize_with_optuna(opt_config)
    elapsed = time.perf_counter() - start_time
    logger.info(
        f"Optuna 优化耗时: {elapsed:.4f}s (平均 {elapsed / 1000 * 1000:.2f}ms/trial)"
    )

    # 同样需要再次运行最优参数以获得完整指标
    logger.info("使用 Optuna 最优参数进行最终验证...")

    # 构建最优参数集
    final_indicators = cfg.indicators_params.copy()
    # 1. 应用指标参数
    for tf, groups in opt_result.best_params.items():
        for group, params in groups.items():
            for p_name, val in params.items():
                final_indicators[tf][group][p_name].value = val

    # 2. 应用回测参数
    final_backtest = cfg.backtest_params
    for p_name, val in opt_result.best_backtest_params.items():
        if hasattr(final_backtest, p_name):
            p_obj = getattr(final_backtest, p_name)
            if isinstance(p_obj, Param):
                p_obj.value = val

    bt_final = Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=final_indicators,
        signal=cfg.signal_params,
        backtest=final_backtest,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
    )
    result_final = bt_final.run()

    # --- 第三阶段: 结果对比打印 ---
    metrics_map = {
        "总回报率": "total_return",
        "最大回撤": "max_drawdown",
        "卡尔玛比率": "calmar_ratio",
    }

    optimized_perf = (
        result_final.summary.performance
        if result_final.summary and result_final.summary.performance
        else {}
    )

    print("\n" + "=" * 60)
    print(f"{'指标':<15} | {'基准 (Baseline)':<18} | {'Optuna 优化后':<18}")
    print("-" * 60)

    for label, key in metrics_map.items():
        base_val = baseline_perf.get(key, 0)
        opt_val = optimized_perf.get(key, 0)

        pref = ""
        if key == "total_return":
            pref = "%"

        print(f"{label:<15} | {base_val:18.4f}{pref} | {opt_val:18.4f}{pref}")

    print("=" * 60)
    print("\n--- Optuna 最优参数 ---")
    print(f"SMA Fast: {opt_result.best_params['ohlcv_15m']['sma_fast']['period']}")
    print(f"SMA Slow: {opt_result.best_params['ohlcv_15m']['sma_slow']['period']}")
    print(f"SL ATR: {opt_result.best_backtest_params.get('sl_atr', 'N/A')}")
    print(f"TSL ATR: {opt_result.best_backtest_params.get('tsl_atr', 'N/A')}")
    print(f"Total Trials: {opt_result.n_trials}")
    print(f"Best Value: {opt_result.best_value:.4f} (CalmarRatioRaw)")

    # 返回结构化摘要，便于 notebook 与 __main__ 复用。
    return {
        "baseline_performance": baseline_perf,
        "optimized_performance": optimized_perf,
        "best_value": opt_result.best_value,
        "n_trials": opt_result.n_trials,
        "best_params": opt_result.best_params,
        "best_backtest_params": opt_result.best_backtest_params,
        "elapsed_seconds": elapsed,
    }


def format_result_for_ai(summary: dict[str, object]) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== OPTUNA_OPTIMIZER_DEMO_RESULT ===")
    lines.append(
        f"n_trials={summary.get('n_trials')}, best_value={summary.get('best_value')}, "
        f"elapsed_seconds={summary.get('elapsed_seconds')}"
    )
    lines.append(f"baseline_performance={summary.get('baseline_performance')}")
    lines.append(f"optimized_performance={summary.get('optimized_performance')}")
    lines.append(f"best_params={summary.get('best_params')}")
    lines.append(f"best_backtest_params={summary.get('best_backtest_params')}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    run_summary = run_optuna_optimizer_demo()
    print(format_result_for_ai(run_summary))
