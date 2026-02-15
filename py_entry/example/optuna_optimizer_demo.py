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

import time


def main():
    logger.info("启动 Optuna 优化器演示...")

    # 1. 模拟数据配置
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=5000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
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

    # --- 第一阶段: 基准回测 ---
    logger.info("执行基准回测 (使用初始参数)...")
    bt = Backtest(
        enable_timing=True,
        data_source=simulated_data_config,
        indicators=indicators_params,
        signal=signal_params,
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
    result = bt.run()

    baseline_perf = (
        result.summary.performance
        if result.summary and result.summary.performance
        else {}
    )

    # --- 第二阶段: Optuna 参数优化 ---
    logger.info("启动 Optuna 参数优化 (1000次)...")
    opt_config = OptunaConfig(
        n_trials=1000,  # 总共尝试 1000 次
        batch_size=50,  # 每批并发 50 个
        metric=OptimizeMetric.CalmarRatioRaw,
        direction="maximize",
        sampler="TPE",  # 使用 TPE 采样器
        seed=42,  # 固定种子以便复现
        show_progress_bar=False,  # 隐藏详细进度条
    )

    start_time = time.perf_counter()
    opt_result = bt.optimize_with_optuna(opt_config)
    elapsed = time.perf_counter() - start_time
    logger.info(
        f"Optuna 优化耗时: {elapsed:.4f}s (平均 {elapsed / 1000 * 1000:.2f}ms/trial)"
    )

    # 同样需要再次运行最优参数以获得完整指标
    logger.info("使用 Optuna 最优参数进行最终验证...")

    # 构建最优参数集
    final_indicators = indicators_params.copy()
    # 1. 应用指标参数
    for tf, groups in opt_result.best_params.items():
        for group, params in groups.items():
            for p_name, val in params.items():
                final_indicators[tf][group][p_name].value = val

    # 2. 应用回测参数
    final_backtest = backtest_params
    for p_name, val in opt_result.best_backtest_params.items():
        if hasattr(final_backtest, p_name):
            p_obj = getattr(final_backtest, p_name)
            if isinstance(p_obj, Param):
                p_obj.value = val

    bt_final = Backtest(
        enable_timing=True,
        data_source=simulated_data_config,
        indicators=final_indicators,
        signal=signal_params,
        backtest=final_backtest,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
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


if __name__ == "__main__":
    main()
