"""趋势共振扫描器主程序"""

import argparse
import time
import logging


# --- 依赖检查 ---
try:
    import tqsdk  # noqa: F401
    import pandas  # noqa: F401
    import pandas_ta  # noqa: F401
    import httpx  # noqa: F401
except ImportError as e:
    raise ImportError(
        f"缺少依赖: {e.name}。\n"
        "请先安装依赖: `just scanner-install`\n"
        "然后运行: `just scanner-run`"
    ) from e

from .config import ScannerConfig
from .data_source import DataSourceProtocol, MockDataSource, TqDataSource
from .resonance import (
    check_timeframe_resonance,
    SymbolResonance,
    get_base_timeframe_config,
    process_adx_for_largest_timeframe,
)
from .notifier import Notifier, format_resonance_report
from .throttler import TimeWindowThrottler

from tqsdk import TqAuth

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner")


def _scan_symbol(
    symbol: str,
    config: ScannerConfig,
    data_source: DataSourceProtocol,
) -> SymbolResonance | None:
    """单独扫描一个品种，返回共振结果"""
    try:
        # 遍历配置的所有周期获取K线
        klines_list = []
        for tf in config.timeframes:
            # print(f"DEBUG: 获取 K线 {symbol} {tf.name}")
            df = data_source.get_klines(symbol, tf.seconds, config.kline_length)
            klines_list.append((tf, df))

        # 检查各周期共振情况
        details = []
        for tf, df in klines_list:
            result = check_timeframe_resonance(df, tf, tf.indicator)
            details.append(result)

        # 必须所有周期都符合做多或所有周期都符合做空
        is_long = all(d.is_bullish for d in details)
        is_short = all(d.is_bearish for d in details)

        if not is_long and not is_short:
            return None

        direction = "long" if is_long else "short"

        # 找到基础周期对应的共振详情作为触发信号
        # 注意：details 顺序与 config.timeframes 顺序一致
        base_tf = get_base_timeframe_config(config.timeframes)
        trigger = "未知"
        for d in details:
            if d.timeframe == base_tf.name:
                trigger = d.detail
                break

        # === 处理最大周期的 ADX ===
        adx_warning = process_adx_for_largest_timeframe(klines_list, details, config)

        resonance = SymbolResonance(
            symbol=symbol,
            direction=direction,
            timeframes=details,
            trigger_signal=trigger,
            adx_warning=adx_warning,
        )
        return resonance

    except (
        ConnectionError,
        TimeoutError,
        OSError,
    ) as e:
        # 只捕获网络IO异常以及预期内的数据计算异常
        # 让其他系统级异常（如 KeyboardInterrupt, SystemExit）冒泡
        logger.error(f"扫描 {symbol} 时出错: {e}")
        import traceback

        traceback.print_exc()
        return None


def scan_and_report(
    symbols: list[str],
    config: ScannerConfig,
    data_source: DataSourceProtocol,
    notifier: Notifier,
) -> list[SymbolResonance]:
    """通用：扫描指定品种列表，收集结果，统一报告，返回共振列表"""
    # 1. 扫描与收集
    results: list[tuple[str, SymbolResonance | None]] = []

    # 为了更好的用户体验，如果是全量扫描且数据还在预热，可以在这里简单通过 get_klines 预热一下内存
    # 但由于上层逻辑通常已经通过 wait(1.0) 保证了数据 freshness，这里直接扫描即可

    for symbol in symbols:
        res = _scan_symbol(symbol, config, data_source)
        results.append((symbol, res))

    # 2. 汇总
    resonances = [r for _, r in results if r is not None]

    # 3. 打印报告
    print("-" * 30)
    if resonances:
        # 使用统一格式化函数打印详情到控制台
        report = format_resonance_report(resonances)
        if report:
            print(report)

        # 统一发送通知
        notifier.notify(resonances)
    else:
        print(f"本次扫描共 {len(results)} 个品种，未发现共振机会。")
    print("-" * 30)

    return resonances


def scan_once(
    config: ScannerConfig, data_source: DataSourceProtocol, notifier: Notifier
):
    """执行单次全量扫描"""
    print(f"执行全量扫描... (品种数: {len(config.symbols)})")
    if not config.symbols:
        logger.warning("没有配置任何监控品种！")
        return

    # 直接调用通用报告函数
    scan_and_report(config.symbols, config, data_source, notifier)
    print("全量扫描完成。")


def scan_forever(
    config: ScannerConfig, data_source: DataSourceProtocol, notifier: Notifier
):
    """执行事件驱动的持续扫描"""
    logger.info("启动事件驱动扫描 (等待 K 线更新...)")

    # 记录每个品种触发周期（列表第一个周期）的最后更新时间
    last_times = {}

    # 基础周期 (触发周期)
    base_tf = get_base_timeframe_config(config.timeframes)

    # 预先订阅/获取一次数据以建立连接
    for symbol in config.symbols:
        df = data_source.get_klines(symbol, base_tf.seconds, config.kline_length)
        if not df.empty:
            last_times[symbol] = df.iloc[-1]["datetime"]

    # 初始全量扫描一次
    scan_once(config, data_source, notifier)

    # 初始化节流器
    base_period = base_tf.seconds
    throttler = TimeWindowThrottler(
        period_seconds=base_period,
        window_seconds=config.throttle_window_seconds,
        heartbeat_interval=config.heartbeat_interval_seconds,
    )
    logger.info(
        f"节流模式开启: 每 {base_period} 秒整点前后 {config.throttle_window_seconds} 秒活跃。"
    )

    while True:
        try:
            # 1. 节流等待 (仅当配置启用时)
            if config.enable_throttler:
                throttler.wait_until_next_window(data_source)

            # 2. 窗口内活跃 wait (1秒)
            data_source.wait(1.0)

            # 醒来后检查是否有 K 线产生新 bar
            updated_symbols = []
            for symbol in config.symbols:
                # 获取最新快照 (基于基础周期)
                df_base = data_source.get_klines(
                    symbol, base_tf.seconds, config.kline_length
                )
                if df_base.empty:
                    continue

                curr_time = df_base.iloc[-1]["datetime"]
                last_time = last_times.get(symbol)

                # 如果时间戳变大，说明新 K 线生成 (收盘确认)
                if last_time is None or curr_time > last_time:
                    last_times[symbol] = curr_time
                    updated_symbols.append(symbol)

            # 如果有品种触发更新，统一扫描报告
            if updated_symbols:
                print(f"检测到 {len(updated_symbols)} 个品种更新，开始扫描...")
                scan_and_report(updated_symbols, config, data_source, notifier)

        except KeyboardInterrupt:
            raise  # 让外层捕获退出
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(f"主循环发生网络异常，5秒后重试: {e}")
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="趋势共振扫描器")
    parser.add_argument("--once", action="store_true", help="单次扫描模式")
    parser.add_argument("--mock", action="store_true", help="使用模拟数据（离线测试）")
    args = parser.parse_args()

    config = ScannerConfig()

    # 打印欢迎语
    print("启动趋势共振扫描器 (事件驱动模式)")
    if args.mock:
        print("模式: Mock (离线模拟)")
    print(f"监控品种: {len(config.symbols)} 个")

    # 初始化数据源
    data_source: DataSourceProtocol  # 明确声明类型为 Protocol
    # print("DEBUG: 正在初始化数据源...")
    try:
        if args.mock:
            data_source = MockDataSource()
        else:
            auth: "TqAuth | None" = None
            if config.tq_username and config.tq_password:
                auth = TqAuth(config.tq_username, config.tq_password)
            elif not config.tq_username:
                logger.error("未配置天勤账号(tq_username)且未使用--mock。")
                logger.error(
                    "请在 data/config.json 中配置账号，或使用 --mock 运行离线测试。"
                )
                return

            data_source = TqDataSource(auth=auth)
    except Exception as e:
        logger.error(f"无法初始化数据源: {e}")
        return
    # print("DEBUG: 数据源初始化完成")

    # print("DEBUG: 正在初始化 Notifier...")
    notifier = Notifier(
        token=config.telegram_bot_token, chat_id=config.telegram_chat_id
    )
    # print("DEBUG: Notifier 初始化完成")

    try:
        if args.once:
            # print("DEBUG: 即将执行 scan_once")
            scan_once(config, data_source, notifier)
            return

        scan_forever(config, data_source, notifier)

    except KeyboardInterrupt:
        logger.info("用户停止扫描器")
    finally:
        data_source.close()
        notifier.close()


if __name__ == "__main__":
    main()
