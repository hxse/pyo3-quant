"""趋势共振扫描器主程序 (多策略版)"""

import argparse
import logging
from typing import NoReturn

# --- 依赖检查 ---
try:
    import tqsdk  # noqa: F401
    import pandas  # noqa: F401
    import pandas_ta  # noqa: F401
    import httpx  # noqa: F401
except ImportError as e:
    print("错误: 缺少必要的依赖库。请运行:")
    print("uv sync")
    print(f"详细错误: {e}")
    exit(1)

from .config import ScannerConfig
from .data_source import DataSourceProtocol, TqDataSource, MockDataSource
from .notifier import Notifier, format_heartbeat, format_signal_report
import traceback
from .throttler import TimeWindowThrottler, CycleTracker
from .utils import get_base_timeframe_config
from .strategies.base import StrategySignal, ScanContext
from .strategies.registry import StrategyRegistry
from .batcher import Batcher
from . import strategies  # noqa: F401 (自动触发策略注册)

from tqsdk import TqAuth

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner")

# === 技巧备注：关于如何彻底静默 TqSdk 的顽固日志 ===
# 1. 软拦截：logging.getLogger("tqsdk").setLevel(logging.ERROR) 只能拦截其通过标准 logging 模块输出的内容。
# 2. 硬拦截：天勤的统计报告（如 胜率、TQSIM 账户总结）往往绕过了 logging，直接通过 print 或 C 扩展写入 stdout/stderr。
# 3. 终极方案：若需在 --once 模式下彻底消除退出时的统计噪音，建议在 finally 块中：
#    with contextlib.redirect_stdout(open(os.devnull, "w")): data_source.close()
# 4. 注意：在 --run (持续扫描) 模式下，这些噪音通常不会触发，因此目前保持代码简洁，不做物理拦截。
# ===============================================


def get_active_strategies(include_debug: bool = False) -> list:
    """获取所有激活的策略实例，根据参数过滤 debug 策略"""
    all_strategies = StrategyRegistry.get_all()
    active_strategies = []
    for cls in all_strategies:
        strategy_instance = cls()
        if not include_debug and strategy_instance.name.startswith("debug"):
            continue
        active_strategies.append(strategy_instance)
    return active_strategies


def _scan_symbol(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    strategies_list: list,
) -> list[StrategySignal]:
    """单独扫描一个品种，运行所有策略"""
    signals = []
    try:
        # P0: 获取真实交易合约 (Underlying)
        # 即使是大周期扫描指数，最终交易的载体还是主力合约
        real_symbol = data_source.get_underlying_symbol(symbol)

        # 1. 准备数据上下文 (获取所有需要的周期)
        # 目前策略主要用: 5m, 1h, 1d, 1w
        # 这些应该在 ScannerConfig.timeframes 里配置了
        # 我们遍历 config.timeframes 来获取数据
        klines_dict = {}
        for tf in config.timeframes:
            # 动态切换数据源: 指数 vs 主连
            target_symbol = symbol
            if tf.use_index:
                # 简单替换：把 KQ.m@ 替换为 KQ.i@
                target_symbol = symbol.replace("KQ.m@", "KQ.i@")

            # print(f"DEBUG: 获取 K线 {target_symbol} {tf.name}")
            df = data_source.get_klines(target_symbol, tf.seconds, config.kline_length)
            if df is not None and not df.empty:
                klines_dict[tf.name] = df

        ctx = ScanContext(symbol=symbol, klines=klines_dict)

        # 2. 运行所有策略
        for strategy in strategies_list:
            try:
                sig = strategy.scan(ctx)
                if sig:
                    # 注入真实合约代码
                    sig.real_symbol = real_symbol
                    signals.append(sig)
            except Exception as e:
                logger.error(f"策略 {strategy.name} 扫描 {symbol} 出错: {e}")

    except (
        ConnectionError,
        TimeoutError,
        OSError,
    ) as e:
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
    """通用：扫描指定品种列表，收集结果，统一报告"""
    all_signals: list[StrategySignal] = []

    for symbol in symbols:
        sigs = _scan_symbol(symbol, config, data_source, strategies_list)
        all_signals.extend(sigs)

    # 打印报告到控制台
    print("-" * 30)
    if config.console_heartbeat_enabled:
        # 心跳模式
        heartbeat_msg = format_heartbeat(len(symbols), all_signals)
        print(heartbeat_msg)
    else:
        # 普通模式
        if all_signals:
            report = format_signal_report(all_signals)
            if report:
                print(report)
        else:
            print(f"本次扫描共 {len(symbols)} 个品种，未发现机会。")
    print("-" * 30)

    # TG 推送
    if all_signals:
        notifier.notify(all_signals)

    return all_signals


def scan_once(
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
    strategies_list: list,
):
    """执行单次全量扫描"""
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
    """执行事件驱动的持续扫描"""
    print("启动持续扫描 (事件驱动模式)...")
    if not config.symbols:
        logger.error("没有配置监控品种，退出。")
        exit(1)

    # 1. 初始化：记录每个品种的最后 K 线时间戳
    last_times: dict[str, int] = {}
    base_tf = get_base_timeframe_config(config.timeframes)

    # 预热数据并记录初始时间戳
    print("正在初始化数据并记录时间戳...")
    for symbol in config.symbols:
        df = data_source.get_klines(symbol, base_tf.seconds, config.kline_length)
        if df is not None and not df.empty:
            last_times[symbol] = df.iloc[-1]["datetime"]

    # 2. 初始化节流器
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

    # 3. 首次先做一次全量，避免启动时静默
    # scan_once(config, data_source, notifier, strategies_list=strategies_list)

    # 5. 初始化防抖批处理器
    batcher = Batcher(buffer_seconds=config.batch_buffer_seconds)

    # 6. 初始化周期追踪器（用于检测新周期开始）
    cycle_tracker = CycleTracker(base_tf.seconds)

    # 7. 主循环
    while True:
        try:
            # A. 节流控制 + 周期检测
            if throttler:
                is_new_cycle = throttler.wait_until_next_window(data_source)
            else:
                is_new_cycle = cycle_tracker.is_new_cycle()

            # B. 窗口内等待 1 秒
            data_source.wait(1.0)

            # C. 新周期签到
            if is_new_cycle:
                batcher.poke()

            # D. 检查是否有 K 线产生新 bar
            for symbol in config.symbols:
                # 获取最新快照 (基于基础周期)
                df_base = data_source.get_klines(
                    symbol, base_tf.seconds, config.kline_length
                )
                if df_base is None or df_base.empty:
                    continue

                curr_time = df_base.iloc[-1]["datetime"]
                last_time = last_times.get(symbol)

                if last_time is None or curr_time > last_time:
                    last_times[symbol] = curr_time

                    # 有 K 线更新时 poke（刷新计时器，延迟 flush）
                    batcher.poke()

                    # 扫描该品种 (得到一组信号)
                    sigs = _scan_symbol(symbol, config, data_source, strategies_list)
                    for sig in sigs:
                        batcher.add(sig)

            # E. 检查是否发车
            if batcher.should_flush():
                batch_signals = batcher.flush()

                # 处理 IO
                print(format_heartbeat(len(config.symbols), batch_signals))
                if batch_signals:
                    notifier.notify(batch_signals)

        except KeyboardInterrupt:
            print("\n用户停止扫描。")
            exit(0)
        except Exception as e:
            # 捕捉天勤运维时间异常或其他网络波动
            msg = str(e)
            if "日常运维时间" in msg or "ConnectionClosedError" in msg:
                logger.warning(f"天勤连接异常 (运维/网络波动): {msg}")
                logger.warning("暂停运行 30 分钟后自动重试...")
                import time

                time.sleep(1800)
            else:
                raise e


def main():
    parser = argparse.ArgumentParser(description="趋势共振扫描器 (Scanner)")
    parser.add_argument(
        "--once", action="store_true", help="只运行一次全量扫描 (默认 run forever)"
    )
    parser.add_argument(
        "--mock", action="store_true", help="使用 Mock 数据源 (离线测试)"
    )
    parser.add_argument(
        "--debug", action="store_true", help="包含以 debug_ 开头的调试策略"
    )
    args = parser.parse_args()

    # 加载配置
    config = ScannerConfig()
    if args.mock:
        config.console_heartbeat_enabled = False  # Mock模式下不打心跳，太刷屏

    # 初始化通知器
    notifier = Notifier(
        token=config.telegram_bot_token, chat_id=config.telegram_chat_id
    )

    # 初始化数据源
    if args.mock:
        print("模式: Mock (离线模拟)")
        data_source = MockDataSource(symbols=config.symbols)
    else:
        print("模式: 实盘数据 (TqSdk)")
        if not config.tq_username or not config.tq_password:
            logger.error("未配置 TqSdk 账户，无法连接实盘数据。")
            exit(1)

        auth = TqAuth(config.tq_username, config.tq_password)
        data_source = TqDataSource(auth=auth)

    print(f"监控品种: {len(config.symbols)} 个")

    # 准备策略
    strategies_instances = get_active_strategies(include_debug=args.debug)
    print(
        f"加载策略: {len(strategies_instances)} 种 -> {[s.name for s in strategies_instances]}"
    )

    try:
        if args.once:
            scan_once(
                config, data_source, notifier, strategies_list=strategies_instances
            )
        else:
            scan_forever(
                config, data_source, notifier, strategies_list=strategies_instances
            )
    finally:
        data_source.close()
        notifier.close()


if __name__ == "__main__":
    main()
