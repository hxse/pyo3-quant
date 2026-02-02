"""通知器 - 日志打印 + 可扩展推送"""

import logging
from datetime import datetime
from .strategies.base import StrategySignal

logger = logging.getLogger("scanner")


def format_signal_report(signals: list[StrategySignal]) -> str:
    """格式化共振报告"""
    if not signals:
        return ""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"趋势共振扫描报告 (共 {len(signals)} 个) [{timestamp}]"]

    for idx, sig in enumerate(signals, 1):
        direction_map = {"long": "做多", "short": "做空", "none": "观察"}
        direction_str = direction_map.get(sig.direction, sig.direction)

        # 详情行拼接
        details_line = " ".join(sig.detail_lines)

        item_str = f"{idx}. {sig.symbol} {sig.strategy_name} {direction_str}\n  - 触发: {sig.trigger}\n  - 详情: {details_line}"

        if sig.warnings:
            # 警告信息
            warn_str = " ".join(sig.warnings)
            item_str += f"\n  - ⚠️ {warn_str}"

        lines.append(item_str)

    return "\n".join(lines).strip()


def format_heartbeat(
    total_symbols: int,
    signals: list[StrategySignal],
) -> str:
    """格式化心跳消息"""
    timestamp = datetime.now().strftime("%H:%M")
    count = len(signals)

    if count > 0:
        # 有共振：简报 + 换行 + 详细报告
        header = f"🔍 {timestamp} | {total_symbols}品种 | {count}信号 ✅"
        detail = format_signal_report(signals)
        return f"{header}\n{detail}"
    else:
        # 无共振：简短一行, 用咖啡杯表示休息
        return f"🔍 {timestamp} | {total_symbols}品种 | 0信号 | 垃圾时间 ☕"


class Notifier:
    """通知器"""

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token
        self.chat_id = chat_id
        if self.token and self.chat_id:
            import httpx

            self.client = httpx.Client(timeout=10.0)
        else:
            self.client = None

    def notify(self, signals: list[StrategySignal]) -> None:
        """发送共振通知"""
        msg = format_signal_report(signals)
        if not msg:
            return

        logger.info(msg)

        if self.client:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": msg}
            try:
                self.client.post(url, json=data)
            except Exception as e:
                logger.error(f"TG推送失败: {e}")

    def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            self.client.close()
