import time
import polars as pl
from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    Param,
    PerformanceParams,
    PerformanceMetric,
    SignalGroup,
    SignalTemplate,
    LogicOp,
    SettingContainer,
    ExecutionStage,
    ParamType,
    OptimizeMetric,
)
from py_entry.data_generator import DirectDataConfig
from .config import STRATEGY_A_PARAMS, STRATEGY_B_PARAMS, STRATEGY_C_PARAMS


def create_backtest(df: pl.DataFrame, strategy: str = "A") -> Backtest:
    """创建回测实例，接受 Polars DataFrame"""
    data_config = DirectDataConfig(
        data={"ohlcv_15m": df},
        base_data_key="ohlcv_15m",
    )

    if strategy == "A":
        # 策略 A: SMA + TSL
        params = STRATEGY_A_PARAMS
        indicators = {
            "ohlcv_15m": {
                "sma_fast": {
                    "period": Param(
                        20,
                        min=params["sma_fast"][0],
                        max=params["sma_fast"][1],
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                },
                "sma_slow": {
                    "period": Param(
                        60,
                        min=params["sma_slow"][0],
                        max=params["sma_slow"][1],
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                },
            }
        }
        backtest_params = BacktestParams(
            initial_capital=10000.0,
            fee_fixed=0.0,
            fee_pct=0.0005,
            tsl_pct=Param(
                0.02,
                min=params["tsl_pct"][0],
                max=params["tsl_pct"][1],
                step=0.005,
                optimize=True,
            ),
            tsl_trigger_mode=True,
            tsl_atr_tight=True,
        )
        signal_template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_fast,ohlcv_15m,0 x> sma_slow,ohlcv_15m,0"],
            ),
            exit_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_fast,ohlcv_15m,0 x< sma_slow,ohlcv_15m,0"],
            ),
        )
    elif strategy == "B":
        # 策略 B: EMA + RSI + TSL
        params = STRATEGY_B_PARAMS
        indicators = {
            "ohlcv_15m": {
                "ema_fast": {
                    "period": Param(
                        12,
                        min=params["ema_fast"][0],
                        max=params["ema_fast"][1],
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                },
                "ema_slow": {
                    "period": Param(
                        26,
                        min=params["ema_slow"][0],
                        max=params["ema_slow"][1],
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                },
                "rsi": {
                    "period": Param(
                        14,
                        min=params["rsi_period"][0],
                        max=params["rsi_period"][1],
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                },
            }
        }
        backtest_params = BacktestParams(
            initial_capital=10000.0,
            fee_fixed=0.0,
            fee_pct=0.0005,
            tsl_pct=Param(
                0.02,
                min=params["tsl_pct"][0],
                max=params["tsl_pct"][1],
                step=0.005,
                optimize=True,
            ),
            tsl_trigger_mode=True,
            tsl_atr_tight=True,
        )
        signal_template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    "ema_fast,ohlcv_15m,0 x> ema_slow,ohlcv_15m,0",
                    "rsi,ohlcv_15m,0 < 50.0",
                ],
            ),
            exit_long=SignalGroup(
                logic=LogicOp.OR,
                comparisons=[
                    "ema_fast,ohlcv_15m,0 x< ema_slow,ohlcv_15m,0",
                    "rsi,ohlcv_15m,0 > 80.0",
                ],
            ),
        )
    elif strategy == "C":
        # 策略 C: 无指标 - 仅价格比较 (close > prev_close)
        # 用于验证指标计算对性能的影响
        params = STRATEGY_C_PARAMS
        indicators = {}  # 无指标
        backtest_params = BacktestParams(
            initial_capital=10000.0,
            fee_fixed=0.0,
            fee_pct=0.0005,
            tsl_pct=Param(
                0.02,
                min=params["tsl_pct"][0],
                max=params["tsl_pct"][1],
                step=0.005,
                optimize=True,
            ),
            tsl_trigger_mode=True,
            tsl_atr_tight=True,
        )
        # 使用价格比较: close[0] > close[1] (当前收盘 > 前收盘)
        signal_template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["close,ohlcv_15m,0 > close,ohlcv_15m,1"],
            ),
            exit_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["close,ohlcv_15m,0 < close,ohlcv_15m,1"],
            ),
        )

    return Backtest(
        enable_timing=False,
        data_source=data_config,
        indicators=indicators,
        backtest=backtest_params,
        signal_template=signal_template,
        performance=PerformanceParams(metrics=[PerformanceMetric.TotalReturn]),
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.Performance, return_only_final=True
        ),
        signal={},
    )


def run_single_backtest(df: pl.DataFrame, strategy: str = "A") -> float:
    """单次回测，返回耗时"""
    bt = create_backtest(df, strategy)
    start = time.perf_counter()
    bt.run()
    return time.perf_counter() - start


def run_optimization(df: pl.DataFrame, samples: int, strategy: str = "A") -> float:
    """参数优化，返回耗时"""
    from py_entry.types import OptimizerConfig

    bt = create_backtest(df, strategy)
    config = OptimizerConfig(
        max_samples=samples,
        samples_per_round=50,
        min_samples=samples,
        stop_patience=9999,
        seed=42,  # 固定随机种子
        optimize_metric=OptimizeMetric.TotalReturn,
    )
    start = time.perf_counter()
    bt.optimize(config)
    return time.perf_counter() - start
