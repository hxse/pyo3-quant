"""扫描器运行时辅助函数。"""

import pandas as pd

from .config import ScanLevel
from .config import ScannerConfig
from .config import TimeframeConfig
from .data_source import DataSourceProtocol
from .strategies.base import ScanContext
from .timeframe_resolver import StrategyRuntimeSpec


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
