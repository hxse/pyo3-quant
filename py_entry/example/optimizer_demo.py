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
)
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def main():
    logger.info("启动增强型优化器演示...")

    # 1. 模拟数据配置
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=10000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. 构建指标参数 (双均线策略)
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param.create(
                    20,
                    min=10,
                    max=40,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.INTEGER,
                ),
            },
            "sma_slow": {
                "period": Param.create(
                    60,
                    min=50,
                    max=100,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.INTEGER,
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
        sl_atr=Param.create(2.5, min=1.0, max=3.0, step=0.1, optimize=True),
        tp_atr=Param.create(2.0, min=1.0, max=3.0, step=0.1, optimize=True),
        tsl_atr=Param.create(2.0, min=1.0, max=3.0, step=0.1, optimize=True),
        atr_period=Param.create(14),
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
        execution_stage=ExecutionStage.PERFORMANCE,
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

    # --- 第二阶段: 参数优化 ---
    logger.info("启动参数优化...")
    opt_config = OptimizerConfig(
        samples_per_round=50,
        min_samples=1000,
        max_samples=2000,
        explore_ratio=0.4,
        stop_patience=10,
    )

    opt_result = bt.optimize(opt_config)

    metrics_map = {
        "总回报率": "total_return",
        "最大回撤": "max_drawdown",
        "卡尔玛比率": "calmar_ratio",
    }

    for label, key in metrics_map.items():
        base_val = baseline_perf.get(key, 0)
        opt_val = (
            opt_result.best_metrics.get("calmar_ratio", 0.0)
            if key == "calmar_ratio"
            else 0
        )
        # 注意: OptimizationResult 目前只直接暴露了 best_calmar。
        # 如果需要获取其他指标，通常需要用最优参数再跑一次 run()。
        # 为了演示，我们先跑一次最优参数的 run。
        pass

    # 获取最优参数再跑一次以获取完整性能指标
    logger.info("使用最优参数进行最终回测以获取完整指标...")
    # 这里简单处理：将 opt_result 的参数应用回 indicators_params 等
    # 我们可以通过 br.setup 重新配置

    final_indicators = indicators_params.copy()
    # 合并指标参数
    # 合并指标参数
    # best_params is SingleParamSet
    for tf, groups in opt_result.best_params.indicators.items():
        for group, params in groups.items():
            for p_name, param in params.items():
                final_indicators[tf][group][p_name].value = param.value

    # 合并回测参数
    final_backtest = backtest_params
    # 合并回测参数
    final_backtest = backtest_params
    # opt_result.best_backtest_params is BacktestParams object
    best_bt = opt_result.best_backtest_params
    # We can iterate over fields or copy common fields
    # Since BacktestParams is a model, we can iterate
    for p_name, p_val in best_bt:
        if isinstance(p_val, Param) and hasattr(final_backtest, p_name):
            p_obj = getattr(final_backtest, p_name)
            if isinstance(p_obj, Param):
                p_obj.value = p_val.value

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
    print("\n" + "=" * 50)
    print(f"{'指标':<15} | {'基准 (Baseline)':<18} | {'优化后 (Optimized)':<18}")
    print("-" * 50)

    optimized_perf = (
        result_final.summary.performance
        if result_final.summary and result_final.summary.performance
        else {}
    )

    for label, key in metrics_map.items():
        base_val = baseline_perf.get(key, 0)
        opt_val = optimized_perf.get(key, 0)

        pref = ""
        if key == "total_return":
            pref = "%"

        print(f"{label:<15} | {base_val:18.4f}{pref} | {opt_val:18.4f}{pref}")

    print("=" * 50)
    print("\n--- 最佳参数详情 ---")
    # Access via indicators
    print(
        f"SMA Fast Period: {opt_result.best_params.indicators['ohlcv_15m']['sma_fast']['period']}"
    )
    print(
        f"SMA Slow Period: {opt_result.best_params.indicators['ohlcv_15m']['sma_slow']['period']}"
    )

    sl_atr = opt_result.best_backtest_params.sl_atr
    print(f"SL ATR Multiplier: {sl_atr.value if sl_atr else 'N/A'}")

    tsl_atr = opt_result.best_backtest_params.tsl_atr
    print(f"TSL ATR Multiplier: {tsl_atr.value if tsl_atr else 'N/A'}")
    print(f"总采样次数: {opt_result.total_samples} | 迭代轮数: {opt_result.rounds}")
    print(
        f"优化目标: {opt_result.optimize_metric.value} | 最优值: {opt_result.optimize_value:.4f}"
    )


if __name__ == "__main__":
    main()
