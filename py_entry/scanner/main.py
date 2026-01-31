"""趋势共振扫描器主程序"""

import argparse
import time
import logging
from typing import TYPE_CHECKING
from .config import ScannerConfig
from .data_source import DataSourceProtocol, MockDataSource, TqDataSource
from .resonance import (
    check_timeframe_resonance,
    SymbolResonance,
    ResonanceLevel,
)
from .notifier import Notifier
from .throttler import TimeWindowThrottler

if TYPE_CHECKING:
    from tqsdk import TqAuth  # type: ignore

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
    notifier: Notifier,
) -> None:
    """单独扫描一个品种"""
    try:
        # 遍历配置的所有周期获取K线
        klines_list = []
        for tf in config.timeframes:
            df = data_source.get_klines(symbol, tf.seconds, config.kline_length)
            klines_list.append((tf, df))

        # 检查各周期共振情况
        details = []
        for tf, df in klines_list:
            result = check_timeframe_resonance(df, tf, config.indicator)
            details.append(result)

        # 必须所有周期都符合做多或所有周期都符合做空
        is_long = all(d.is_bullish for d in details)
        is_short = all(d.is_bearish for d in details)

        if not is_long and not is_short:
            return

        direction = "long" if is_long else "short"

        # 简化模式：只检测品种自身共振
        level = ResonanceLevel.FOUR_STAR

        # 使用第一个周期（通常是最小周期）的详情作为触发描述
        trigger = details[0].detail

        resonance = SymbolResonance(
            symbol=symbol,
            direction=direction,
            level=level,
            timeframes=details,
            trigger_signal=trigger,
        )
        logger.info(f"发现共振: {symbol} {direction}")
        notifier.notify([resonance])

    except Exception as e:
        logger.error(f"扫描 {symbol} 时出错: {e}")
        import traceback

        traceback.print_exc()


def scan_once(
    config: ScannerConfig, data_source: DataSourceProtocol, notifier: Notifier
):
    """执行单次全量扫描"""
    logger.info("执行全量扫描...")
    for symbol in config.symbols:
        _scan_symbol(symbol, config, data_source, notifier)
    logger.info("全量扫描完成。")


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
    try:
        if args.mock:
            data_source = MockDataSource()
        else:
            # 动态导入防止无 tqsdk 环境报错
            try:
                from tqsdk import TqAuth  # type: ignore
            except ImportError:
                # 给个假的或者再次抛出，这里应该有环境
                pass

            auth: "TqAuth | None" = None
            if config.tq_username and config.tq_password:
                auth = TqAuth(config.tq_username, config.tq_password)
            elif not config.tq_username:
                logger.warning("未配置天勤账号(tq_username)且未使用--mock。")
                logger.warning(
                    "请在 config.py 中配置账号，或使用 --mock 运行离线测试。"
                )
                # 这里不报错，让它尝试（虽然 TqSdk 新版大概率回报错）

            data_source = TqDataSource(auth=auth)
    except Exception as e:
        logger.error(f"无法初始化数据源: {e}")
        return

    notifier = Notifier(
        token=config.telegram_bot_token, chat_id=config.telegram_chat_id
    )

    try:
        if args.once:
            scan_once(config, data_source, notifier)
            return

        logger.info("启动事件驱动扫描 (等待 K 线更新...)")

        # 记录每个品种触发周期（列表第一个周期）的最后更新时间
        last_times = {}

        # 基础周期取列表中的第一个（即触发周期，如 5m 或 3m）
        base_tf = config.timeframes[0]

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

                        # 触发单品种扫描
                        _scan_symbol(symbol, config, data_source, notifier)

            except KeyboardInterrupt:
                raise  # 让外层捕获退出
            except Exception as e:
                logger.error(f"主循环发生异常，5秒后重试: {e}")
                time.sleep(5)

    except KeyboardInterrupt:
        logger.info("用户停止扫描器")
    finally:
        data_source.close()


if __name__ == "__main__":
    main()
