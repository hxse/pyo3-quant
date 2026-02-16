"""趋势共振扫描器主程序 (多策略版)"""

import argparse
import logging

# --- 依赖检查 ---
try:
    import tqsdk  # type: ignore # noqa: F401
    import pandas  # noqa: F401
    import pandas_ta  # noqa: F401
    import httpx  # noqa: F401
except ImportError as e:
    print("错误: 缺少必要的依赖库。请运行:")
    print("uv sync")
    print(f"详细错误: {e}")
    exit(1)

from tqsdk import TqAuth  # type: ignore

from . import strategies  # noqa: F401 (自动触发策略注册)
from ._scan_runtime import get_active_strategies
from ._scan_runtime import scan_forever
from ._scan_runtime import scan_once
from .config import ScannerConfig
from .data_source import MockDataSource
from .data_source import TqDataSource
from .notifier import Notifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scanner")


def main() -> None:
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

    config = ScannerConfig()
    if args.mock:
        config.console_heartbeat_enabled = False

    notifier = Notifier(
        token=config.telegram_bot_token, chat_id=config.telegram_chat_id
    )

    if args.mock:
        print("模式: Mock (离线模拟)")
        data_source = MockDataSource(config=config)
    else:
        print("模式: 实盘数据 (TqSdk)")
        if not config.tq_username or not config.tq_password:
            logger.error("未配置 TqSdk 账户，无法连接实盘数据。")
            exit(1)

        auth = TqAuth(config.tq_username, config.tq_password)
        data_source = TqDataSource(auth=auth)

    print(f"监控品种: {len(config.symbols)} 个")

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
