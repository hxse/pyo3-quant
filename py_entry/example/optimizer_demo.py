import time
from loguru import logger
from py_entry.runner import BacktestRunner, SetupConfig
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


def main():
    logger.info("启动增强型优化器演示...")

    # 1. 模拟数据配置
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=5000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. 构建指标参数 (双均线策略)
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param.create(
                    20,
                    initial_min=10,
                    initial_max=40,
                    step=1.0,
                    optimize=True,
                    dtype=ParamType.INTEGER,
                ),
            },
            "sma_slow": {
                "period": Param.create(
                    60,
                    initial_min=50,
                    initial_max=200,
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
        sl_atr=Param.create(
            2.5, initial_min=1.0, initial_max=3.0, step=0.1, optimize=True
        ),
        tsl_atr=Param.create(
            2.0, initial_min=1.0, initial_max=3.0, step=0.1, optimize=True
        ),
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

    # 初始化 Runner
    br = BacktestRunner()

    # --- 第一阶段: 基准回测 ---
    logger.info("执行基准回测 (使用初始参数)...")
    br.setup(
        SetupConfig(
            enable_timing=True,
            data_source=simulated_data_config,
            indicators=indicators_params,
            signal=signal_params,
            backtest=backtest_params,
            performance=performance_params,
            signal_template=signal_template,
            engine_settings=engine_settings,
        )
    ).run()

    baseline_perf = br.results[0].performance if br.results else {}

    # --- 第二阶段: 参数优化 ---
    logger.info("启动参数优化...")
    opt_config = OptimizerConfig(
        samples_per_round=50,
        min_samples=500,
        max_samples=2000,
        explore_ratio=0.4,
        stop_patience=10,
    )

    opt_result = br.optimize(opt_config)

    metrics_map = {
        "总回报率": "total_return",
        "最大回撤": "max_drawdown",
        "卡尔玛比率": "calmar_ratio",
    }

    for label, key in metrics_map.items():
        base_val = baseline_perf.get(key, 0)
        opt_val = (
            opt_result.best_calmar if key == "calmar_ratio" else 0
        )  # OptimizationResult 暂时只传回了 best_calmar
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
    for tf, groups in opt_result.best_params.items():
        for group, params in groups.items():
            for p_name, val in params.items():
                final_indicators[tf][group][p_name].value = val

    # 合并回测参数
    final_backtest = backtest_params
    for p_name, val in opt_result.best_backtest_params.items():
        if hasattr(final_backtest, p_name):
            p_obj = getattr(final_backtest, p_name)
            if isinstance(p_obj, Param):
                p_obj.value = val

    br.setup(
        SetupConfig(
            data_source=simulated_data_config,
            indicators=final_indicators,
            signal=signal_params,
            backtest=final_backtest,
            performance=performance_params,
            signal_template=signal_template,
            engine_settings=engine_settings,
        )
    ).run()

    # --- 第三阶段: 结果对比打印 ---
    print("\n" + "=" * 50)
    print(f"{'指标':<15} | {'基准 (Baseline)':<18} | {'优化后 (Optimized)':<18}")
    print("-" * 50)

    optimized_perf = br.results[0].performance if br.results else {}

    for label, key in metrics_map.items():
        base_val = baseline_perf.get(key, 0)
        opt_val = optimized_perf.get(key, 0)

        pref = ""
        if key == "total_return":
            pref = "%"

        print(f"{label:<15} | {base_val:18.4f}{pref} | {opt_val:18.4f}{pref}")

    print("=" * 50)
    print("\n--- 最佳参数详情 ---")
    print(
        f"SMA Fast Period: {opt_result.best_params['ohlcv_15m']['sma_fast']['period']}"
    )
    print(
        f"SMA Slow Period: {opt_result.best_params['ohlcv_15m']['sma_slow']['period']}"
    )
    print(f"SL ATR Multiplier: {opt_result.best_backtest_params.get('sl_atr', 'N/A')}")
    print(
        f"TSL ATR Multiplier: {opt_result.best_backtest_params.get('tsl_atr', 'N/A')}"
    )
    print(f"总采样次数: {opt_result.total_samples} | 迭代轮数: {opt_result.rounds}")


if __name__ == "__main__":
    main()
