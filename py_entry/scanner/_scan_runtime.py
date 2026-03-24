"""扫描器运行时流程（从 main 拆分）。"""

import logging
import traceback
from typing import NoReturn

import pandas as pd

from .batcher import Batcher
from .config import ScanLevel
from .config import ScannerConfig
from .config import TimeframeConfig
from .data_source import DataSourceProtocol
from .notifier import Notifier
from .notifier import format_heartbeat
from .notifier import format_signal_report
from .strategies.base import ScanContext
from .strategies.base import StrategyBase
from .strategies.base import StrategySignal
from .strategies.registry import StrategyRegistry
from .throttler import CycleTracker
from .throttler import TimeWindowThrottler
from .timeframe_resolver import StrategyRuntimeSpec
from .timeframe_resolver import collect_required_timeframes
from .timeframe_resolver import get_min_watch_timeframe
from .timeframe_resolver import resolve_strategy_runtime_specs

logger = logging.getLogger("scanner")


def get_active_strategies(
    include_debug: bool = False, enabled_names: list[str] | None = None
) -> list[StrategyBase]:
    """获取激活策略实例，并按配置名单过滤。"""
    all_strategies = StrategyRegistry.get_all()
    enabled_name_set = set(enabled_names or [])
    registry_name_set = set(StrategyRegistry.list_names())

    if enabled_name_set:
        unknown_names = sorted(enabled_name_set - registry_name_set)
        if unknown_names:
            logger.warning(f"配置中存在未注册策略，将忽略: {unknown_names}")

    active_strategies: list[StrategyBase] = []
    for cls in all_strategies:
        strategy_instance = cls()
        if not include_debug and strategy_instance.name.startswith("debug"):
            continue
        if enabled_name_set and strategy_instance.name not in enabled_name_set:
            continue
        active_strategies.append(strategy_instance)
    return active_strategies


def build_runtime_specs(
    config: ScannerConfig, strategies_list: list[StrategyBase]
) -> tuple[list[StrategyRuntimeSpec], dict[str, TimeframeConfig]]:
    """构造策略运行时画像与全局所需周期并集。"""
    runtime_specs = resolve_strategy_runtime_specs(strategies_list, config.timeframes)
    required_timeframes = collect_required_timeframes(runtime_specs)
    return runtime_specs, required_timeframes


def _get_target_symbol(symbol: str, tf: TimeframeConfig) -> str:
    """根据周期配置选择主连或指数合约。"""
    if tf.use_index:
        return symbol.replace("KQ.m@", "KQ.i@")
    return symbol


def _fetch_symbol_klines(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    timeframes: dict[str, TimeframeConfig],
) -> dict[str, pd.DataFrame]:
    """按给定周期集合拉取某个品种所需的 K 线数据。"""
    klines_dict: dict[str, pd.DataFrame] = {}
    for tf in timeframes.values():
        target_symbol = _get_target_symbol(symbol, tf)
        df = data_source.get_klines(target_symbol, tf.seconds, config.kline_length)
        if df is not None and not df.empty:
            klines_dict[tf.storage_key] = df
    return klines_dict


def _ensure_required_klines(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    required_timeframes: dict[str, TimeframeConfig],
    preloaded_klines: dict[str, pd.DataFrame] | None,
) -> dict[str, pd.DataFrame]:
    """确保扫描所需周期齐全；若已预取部分数据，则只补拉缺失周期。"""
    if preloaded_klines is None:
        return _fetch_symbol_klines(symbol, config, data_source, required_timeframes)

    missing_timeframes = {
        storage_key: tf
        for storage_key, tf in required_timeframes.items()
        if storage_key not in preloaded_klines
    }
    if not missing_timeframes:
        return preloaded_klines

    completed_klines = dict(preloaded_klines)
    completed_klines.update(
        _fetch_symbol_klines(symbol, config, data_source, missing_timeframes)
    )
    return completed_klines


def _collect_updated_watch_klines(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    base_watch_tf: TimeframeConfig,
    watch_timeframes: dict[str, TimeframeConfig],
    last_times: dict[str, int],
) -> tuple[dict[str, pd.DataFrame], set[str]]:
    """只轮询最小 watch 周期；命中心跳后再补查其他 watch 周期。"""
    base_storage_key = base_watch_tf.storage_key
    base_klines = _fetch_symbol_klines(
        symbol,
        config,
        data_source,
        {base_storage_key: base_watch_tf},
    )
    base_df = base_klines.get(base_storage_key)
    if base_df is None or base_df.empty:
        return {}, set()

    curr_time = base_df.iloc[-1]["datetime"]
    last_time = last_times.get(base_storage_key)
    if last_time is not None and curr_time <= last_time:
        return {}, set()

    last_times[base_storage_key] = curr_time
    updated_storage_keys = {base_storage_key}
    preloaded_klines = dict(base_klines)

    other_watch_timeframes = {
        storage_key: tf
        for storage_key, tf in watch_timeframes.items()
        if storage_key != base_storage_key
    }
    if not other_watch_timeframes:
        return preloaded_klines, updated_storage_keys

    other_watch_klines = _fetch_symbol_klines(
        symbol,
        config,
        data_source,
        other_watch_timeframes,
    )
    preloaded_klines.update(other_watch_klines)

    for storage_key, df in other_watch_klines.items():
        if df is None or df.empty:
            continue
        curr_time = df.iloc[-1]["datetime"]
        last_time = last_times.get(storage_key)
        if last_time is None or curr_time > last_time:
            last_times[storage_key] = curr_time
            updated_storage_keys.add(storage_key)

    return preloaded_klines, updated_storage_keys


def _resolve_updated_levels(
    runtime_spec: StrategyRuntimeSpec,
    updated_storage_keys: set[str] | None,
) -> set[ScanLevel]:
    """把 storage_key 级别的更新集合翻译回策略自己的逻辑级别集合。"""
    if updated_storage_keys is None:
        return set(runtime_spec.level_to_tf.keys())

    return {
        level
        for level, storage_key in runtime_spec.level_to_tf.items()
        if storage_key in updated_storage_keys
    }


def _build_strategy_context(
    symbol: str,
    klines_dict: dict[str, pd.DataFrame],
    required_timeframes: dict[str, TimeframeConfig],
    runtime_spec: StrategyRuntimeSpec,
    updated_storage_keys: set[str] | None,
) -> ScanContext:
    """为单个策略构造上下文，只暴露它声明过的周期画像。"""
    required_keys = set(runtime_spec.level_to_tf.values())
    return ScanContext(
        symbol=symbol,
        klines={
            storage_key: klines_dict[storage_key]
            for storage_key in required_keys
            if storage_key in klines_dict
        },
        timeframes={
            storage_key: required_timeframes[storage_key]
            for storage_key in required_keys
        },
        level_to_tf=runtime_spec.level_to_tf,
        updated_levels=_resolve_updated_levels(runtime_spec, updated_storage_keys),
    )


def scan_symbol(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    runtime_specs: list[StrategyRuntimeSpec],
    required_timeframes: dict[str, TimeframeConfig],
    preloaded_klines: dict[str, pd.DataFrame] | None = None,
    updated_storage_keys: set[str] | None = None,
) -> list[StrategySignal]:
    """扫描单个品种并运行需要触发的策略。"""
    signals: list[StrategySignal] = []
    try:
        real_symbol = data_source.get_underlying_symbol(symbol)
        klines_dict = _ensure_required_klines(
            symbol=symbol,
            config=config,
            data_source=data_source,
            required_timeframes=required_timeframes,
            preloaded_klines=preloaded_klines,
        )

        for runtime_spec in runtime_specs:
            if (
                updated_storage_keys is not None
                and runtime_spec.watch_storage_keys.isdisjoint(updated_storage_keys)
            ):
                continue

            try:
                ctx = _build_strategy_context(
                    symbol=symbol,
                    klines_dict=klines_dict,
                    required_timeframes=required_timeframes,
                    runtime_spec=runtime_spec,
                    updated_storage_keys=updated_storage_keys,
                )
                sig = runtime_spec.strategy.scan(ctx)
                if sig:
                    sig.real_symbol = real_symbol
                    signals.append(sig)
            except Exception as e:
                logger.error(
                    f"策略 {runtime_spec.strategy.name} 扫描 {symbol} 出错: {e}"
                )
                traceback.print_exc()

    except (ConnectionError, TimeoutError, OSError) as e:
        logger.error(f"扫描 {symbol} 时数据获取出错: {e}")
        traceback.print_exc()

    return signals


def scan_and_report(
    symbols: list[str],
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
    runtime_specs: list[StrategyRuntimeSpec],
    required_timeframes: dict[str, TimeframeConfig],
) -> list[StrategySignal]:
    """通用扫描入口：扫描指定品种并统一输出报告。"""
    all_signals: list[StrategySignal] = []

    for symbol in symbols:
        sigs = scan_symbol(
            symbol,
            config,
            data_source,
            runtime_specs=runtime_specs,
            required_timeframes=required_timeframes,
        )
        all_signals.extend(sigs)

    print("-" * 30)
    if config.console_heartbeat_enabled:
        heartbeat_msg = format_heartbeat(len(symbols), all_signals)
        print(heartbeat_msg)
    else:
        if all_signals:
            report = format_signal_report(all_signals)
            if report:
                print(report)
        else:
            print(f"本次扫描共 {len(symbols)} 个品种，未发现机会。")
    print("-" * 30)

    if all_signals:
        notifier.notify(all_signals)

    return all_signals


def scan_once(
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
    runtime_specs: list[StrategyRuntimeSpec],
    required_timeframes: dict[str, TimeframeConfig],
) -> None:
    """执行单次全量扫描。"""
    print(f"执行全量扫描... (品种数: {len(config.symbols)})")
    if not config.symbols:
        logger.warning("没有配置任何监控品种！")
        return

    scan_and_report(
        config.symbols,
        config,
        data_source,
        notifier,
        runtime_specs=runtime_specs,
        required_timeframes=required_timeframes,
    )
    print("全量扫描完成。")


def scan_forever(
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
    runtime_specs: list[StrategyRuntimeSpec],
    required_timeframes: dict[str, TimeframeConfig],
) -> NoReturn:
    """执行事件驱动的持续扫描。"""
    print("启动持续扫描 (事件驱动模式)...")
    if not config.symbols:
        logger.error("没有配置监控品种，退出。")
        exit(1)

    watch_storage_keys = {
        storage_key for spec in runtime_specs for storage_key in spec.watch_storage_keys
    }
    watch_timeframes = {
        storage_key: required_timeframes[storage_key]
        for storage_key in watch_storage_keys
    }
    last_times: dict[str, dict[str, int]] = {}

    base_tf = get_min_watch_timeframe(runtime_specs, required_timeframes)

    print("正在初始化数据并记录时间戳...")
    for symbol in config.symbols:
        klines_dict = _fetch_symbol_klines(
            symbol, config, data_source, watch_timeframes
        )
        symbol_last_times: dict[str, int] = {}
        for storage_key in watch_storage_keys:
            df = klines_dict.get(storage_key)
            if df is not None and not df.empty:
                symbol_last_times[storage_key] = df.iloc[-1]["datetime"]
        last_times[symbol] = symbol_last_times

    throttler = None
    if config.enable_throttler:
        throttler = TimeWindowThrottler(
            period_seconds=base_tf.seconds,
            window_seconds=config.throttle_window_seconds,
            heartbeat_interval=config.heartbeat_interval_seconds,
        )
        logger.info(
            f"节流模式已开启: 周期={base_tf.name}({base_tf.seconds}s), 窗口={config.throttle_window_seconds}s"
        )
    else:
        logger.info("节流模式未开启 (全天候运行)")

    batcher = Batcher(buffer_seconds=config.batch_buffer_seconds)
    cycle_tracker = CycleTracker(base_tf.seconds)

    while True:
        try:
            if throttler:
                is_new_cycle = throttler.wait_until_next_window(data_source)
            else:
                is_new_cycle = cycle_tracker.is_new_cycle()

            data_source.wait(1.0)

            if is_new_cycle:
                batcher.poke()

            for symbol in config.symbols:
                symbol_last_times = last_times.setdefault(symbol, {})
                preloaded_watch_klines, updated_storage_keys = (
                    _collect_updated_watch_klines(
                        symbol=symbol,
                        config=config,
                        data_source=data_source,
                        base_watch_tf=base_tf,
                        watch_timeframes=watch_timeframes,
                        last_times=symbol_last_times,
                    )
                )

                if not updated_storage_keys:
                    continue

                batcher.poke()
                sigs = scan_symbol(
                    symbol=symbol,
                    config=config,
                    data_source=data_source,
                    runtime_specs=runtime_specs,
                    required_timeframes=required_timeframes,
                    preloaded_klines=preloaded_watch_klines,
                    updated_storage_keys=updated_storage_keys,
                )
                for sig in sigs:
                    batcher.add(sig)

            if batcher.should_flush():
                batch_signals = batcher.flush()
                print(format_heartbeat(len(config.symbols), batch_signals))
                if batch_signals:
                    notifier.notify(batch_signals)

        except KeyboardInterrupt:
            print("\n用户停止扫描。")
            exit(0)
        except Exception as e:
            msg = str(e)
            if "每日 19:00-19:30 为日常运维时间，请稍后再试" in msg:
                logger.warning(f"天勤连接异常 (运维/网络波动): {msg}")
                logger.warning("暂停运行 30 分钟后自动重试...")
                import time

                time.sleep(1800)
            else:
                raise e
