"""扫描器运行时流程（从 main 拆分）。"""

import logging
import traceback
from typing import NoReturn

from .batcher import Batcher
from .config import ScanLevel
from .config import ScannerConfig
from .config import TimeframeConfig
from .data_source import DataSourceProtocol
from .notifier import Notifier
from .notifier import format_heartbeat
from .notifier import format_signal_report
from .strategies.base import ScanContext
from .strategies.base import StrategySignal
from .strategies.registry import StrategyRegistry
from .throttler import CycleTracker
from .throttler import TimeWindowThrottler

logger = logging.getLogger("scanner")


def get_active_strategies(include_debug: bool = False) -> list:
    """获取所有激活策略实例，根据参数过滤 debug 策略。"""
    all_strategies = StrategyRegistry.get_all()
    active_strategies = []
    for cls in all_strategies:
        strategy_instance = cls()
        if not include_debug and strategy_instance.name.startswith("debug"):
            continue
        active_strategies.append(strategy_instance)
    return active_strategies


def scan_symbol(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    strategies_list: list,
) -> list[StrategySignal]:
    """扫描单个品种并运行所有策略。"""
    signals = []
    try:
        real_symbol = data_source.get_underlying_symbol(symbol)

        klines_dict = {}
        level_to_tf = {}
        for tf in config.timeframes:
            level_to_tf[tf.level] = tf.name

            target_symbol = symbol
            if tf.use_index:
                target_symbol = symbol.replace("KQ.m@", "KQ.i@")

            df = data_source.get_klines(target_symbol, tf.seconds, config.kline_length)
            if df is not None and not df.empty:
                klines_dict[tf.name] = df

        ctx = ScanContext(symbol=symbol, klines=klines_dict, level_to_tf=level_to_tf)

        for strategy in strategies_list:
            try:
                sig = strategy.scan(ctx)
                if sig:
                    sig.real_symbol = real_symbol
                    signals.append(sig)
            except Exception as e:
                logger.error(f"策略 {strategy.name} 扫描 {symbol} 出错: {e}")
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
    strategies_list: list,
) -> list[StrategySignal]:
    """通用扫描入口：扫描指定品种并统一输出报告。"""
    all_signals: list[StrategySignal] = []

    for symbol in symbols:
        sigs = scan_symbol(symbol, config, data_source, strategies_list)
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
    strategies_list: list,
) -> None:
    """执行单次全量扫描。"""
    print(f"执行全量扫描... (品种数: {len(config.symbols)})")
    if not config.symbols:
        logger.warning("没有配置任何监控品种！")
        return

    scan_and_report(
        config.symbols, config, data_source, notifier, strategies_list=strategies_list
    )
    print("全量扫描完成。")


def scan_forever(
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
    strategies_list: list,
) -> NoReturn:
    """执行事件驱动的持续扫描。"""
    print("启动持续扫描 (事件驱动模式)...")
    if not config.symbols:
        logger.error("没有配置监控品种，退出。")
        exit(1)

    last_times: dict[str, int] = {}

    base_tf_found = next(
        (tf for tf in config.timeframes if tf.level == ScanLevel.TRIGGER), None
    )
    if base_tf_found is None:
        logger.error(f"配置中缺少 {ScanLevel.TRIGGER}，无法确定主循环周期。")
        exit(1)

    assert base_tf_found is not None
    base_tf: TimeframeConfig = base_tf_found

    print("正在初始化数据并记录时间戳...")
    for symbol in config.symbols:
        df = data_source.get_klines(symbol, base_tf.seconds, config.kline_length)
        if df is not None and not df.empty:
            last_times[symbol] = df.iloc[-1]["datetime"]

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
                df_base = data_source.get_klines(
                    symbol, base_tf.seconds, config.kline_length
                )
                if df_base is None or df_base.empty:
                    continue

                curr_time = df_base.iloc[-1]["datetime"]
                last_time = last_times.get(symbol)

                if last_time is None or curr_time > last_time:
                    last_times[symbol] = curr_time
                    batcher.poke()

                    sigs = scan_symbol(symbol, config, data_source, strategies_list)
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
