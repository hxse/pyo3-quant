import polars as pl

from .bot_config import BotConfig
from .callbacks import Callbacks
from .executor import ActionExecutor
from .optimization import OptimizationCallbacks
from .runtime_checks import RuntimeChecks
from .signal import SignalState
from .strategy_params import StrategyParams
from ._bot_signal_execution import StepResult, execute_signal


async def process_symbol(
    callbacks: Callbacks,
    config: BotConfig,
    params: StrategyParams,
) -> StepResult:
    """处理单个品种。"""
    # 为单个 symbol 建立作用域代理，避免同轮重复调用。
    scoped_callbacks = OptimizationCallbacks(callbacks, params.symbol)
    scoped_runtime_checks = RuntimeChecks(scoped_callbacks)
    scoped_executor = ActionExecutor(scoped_callbacks, scoped_runtime_checks)

    ohlcv_result = callbacks.fetch_ohlcv(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
        symbol=params.symbol,
        timeframe=params.base_data_key.split("_")[-1],
        since=None,
        limit=500,
        enable_cache=True,
        enable_test=False,
    )
    if not ohlcv_result.success:
        return StepResult(
            success=False, message=f"fetch_ohlcv failed: {ohlcv_result.message}"
        )

    ohlcv_data = ohlcv_result.data or []
    dataframe = pl.DataFrame(
        ohlcv_data,
        schema=["timestamp", "open", "high", "low", "close", "volume"],
        orient="row",
    )

    backtest_result = callbacks.run_backtest(params, dataframe)
    if not backtest_result.success:
        return StepResult(
            success=False,
            message=f"run_backtest failed: {backtest_result.message}",
        )

    backtest_dataframe = backtest_result.data
    if backtest_dataframe is None:
        return StepResult(success=False, message="Backtest data is None")

    curr_result = callbacks.parse_signal(backtest_dataframe, params, index=-1)
    if not curr_result.success:
        return StepResult(
            success=False,
            message=f"parse_signal (curr) failed: {curr_result.message}",
        )
    curr_signal = curr_result.data
    if curr_signal is None:
        return StepResult(success=False, message="Current signal is None")

    prev_result = callbacks.parse_signal(backtest_dataframe, params, index=-2)
    if not prev_result.success:
        return StepResult(
            success=False,
            message=f"parse_signal (prev) failed: {prev_result.message}",
        )
    prev_signal = prev_result.data
    if prev_signal is None:
        return StepResult(success=False, message="Previous signal is None")

    return execute_signal(
        callbacks=callbacks,
        config=config,
        params=params,
        curr_signal=curr_signal,
        prev_signal=prev_signal,
        runtime_checks=scoped_runtime_checks,
        executor=scoped_executor,
    )


def default_signal_state(signal: SignalState | None) -> SignalState:
    """保证单步执行时总能拿到有效信号对象。"""
    return signal or SignalState(actions=[])
