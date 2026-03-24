from dataclasses import dataclass

from py_entry.scanner.config import ScanLevel, TimeframeConfig
from py_entry.scanner.strategies.base import StrategyBase


@dataclass
class StrategyRuntimeSpec:
    """策略运行时画像：固定某个策略本次扫描的周期映射与监听集合。"""

    strategy: StrategyBase
    timeframes: list[TimeframeConfig]
    level_to_tf: dict[ScanLevel, str]
    watch_storage_keys: set[str]


def _validate_profile_timeframes(timeframes: list[TimeframeConfig]) -> None:
    """校验单个策略画像本身是否自洽。"""
    level_to_storage: dict[ScanLevel, str] = {}
    timeframe_names: set[str] = set()
    for tf in timeframes:
        existed_storage = level_to_storage.get(tf.level)
        if existed_storage is not None:
            raise ValueError(
                f"策略周期画像存在重复逻辑级别: {tf.level} -> {existed_storage}, {tf.storage_key}"
            )
        level_to_storage[tf.level] = tf.storage_key

        if tf.name in timeframe_names:
            raise ValueError(
                f"单个策略画像中存在重复物理周期名: {tf.name}。"
                "当前 scanner 约定同一策略内每个物理周期名必须唯一。"
            )
        timeframe_names.add(tf.name)


def build_level_to_tf(timeframes: list[TimeframeConfig]) -> dict[ScanLevel, str]:
    """将周期画像转换为逻辑级别到 storage_key 的映射。"""
    _validate_profile_timeframes(timeframes)
    return {tf.level: tf.storage_key for tf in timeframes}


def resolve_strategy_runtime_specs(
    strategies: list[StrategyBase], default_timeframes: list[TimeframeConfig]
) -> list[StrategyRuntimeSpec]:
    """解析所有策略的有效周期画像与监听集合。"""
    runtime_specs: list[StrategyRuntimeSpec] = []
    for strategy in strategies:
        effective_timeframes = strategy.get_timeframes(default_timeframes)
        level_to_tf = build_level_to_tf(effective_timeframes)

        watch_storage_keys: set[str] = set()
        for level in strategy.get_watch_levels():
            storage_key = level_to_tf.get(level)
            if storage_key is None:
                raise ValueError(f"策略 {strategy.name} 监听了未声明的级别: {level}")
            watch_storage_keys.add(storage_key)

        runtime_specs.append(
            StrategyRuntimeSpec(
                strategy=strategy,
                timeframes=effective_timeframes,
                level_to_tf=level_to_tf,
                watch_storage_keys=watch_storage_keys,
            )
        )

    return runtime_specs


def collect_required_timeframes(
    runtime_specs: list[StrategyRuntimeSpec],
) -> dict[str, TimeframeConfig]:
    """合并所有策略需要的物理周期；全局只拉取并缓存一次。"""
    required: dict[str, TimeframeConfig] = {}
    for spec in runtime_specs:
        for tf in spec.timeframes:
            existed = required.get(tf.storage_key)
            if existed is None:
                required[tf.storage_key] = tf
                continue

            if (
                existed.name != tf.name
                or existed.seconds != tf.seconds
                or existed.use_index != tf.use_index
            ):
                raise ValueError(
                    f"相同 storage_key 对应了不同周期定义: {tf.storage_key}"
                )

    return required


def get_min_watch_timeframe(
    runtime_specs: list[StrategyRuntimeSpec],
    required_timeframes: dict[str, TimeframeConfig],
) -> TimeframeConfig:
    """获取所有监听周期中的最小周期，用于驱动外层节流循环。"""
    watch_storage_keys = {
        storage_key for spec in runtime_specs for storage_key in spec.watch_storage_keys
    }
    if not watch_storage_keys:
        raise ValueError("未配置任何监听周期，无法启动扫描循环")

    return min(
        (required_timeframes[storage_key] for storage_key in watch_storage_keys),
        key=lambda tf: tf.seconds,
    )
