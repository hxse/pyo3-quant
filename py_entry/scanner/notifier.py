"""通知器 - 日志打印 + 可扩展推送"""

import logging
from datetime import datetime
from .resonance import SymbolResonance

logger = logging.getLogger("scanner")


def format_resonance_report(resonances: list[SymbolResonance]) -> str:
    """格式化共振报告"""
    if not resonances:
        return ""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [f"趋势共振扫描报告 (共 {len(resonances)} 个) [{timestamp}]"]

    for idx, r in enumerate(resonances, 1):
        direction = "做多" if r.direction == "long" else "做空"

        details_parts = []
        for t in r.timeframes:
            # 显示周期、价格和详情 (以及额外信息如 ADX)
            text = t.detail
            if t.extra_info:
                text += f" {t.extra_info}"
            details_parts.append(f"[{t.timeframe} @ {t.price:.1f}] {text}")

        details_line = " ".join(details_parts)

        item_str = f"{idx}. {r.symbol} {direction}\n  - 详情: {details_line}"

        if r.adx_warning:
            item_str += f"\n  - {r.adx_warning}"

        lines.append(item_str)

    return "\n".join(lines).strip()


def format_heartbeat(
    total_symbols: int,
    resonances: list[SymbolResonance],
) -> str:
    """格式化心跳消息"""
    timestamp = datetime.now().strftime("%H:%M")
    count = len(resonances)

    if count > 0:
        # 有共振：简报 + 换行 + 详细报告
        # 注意：详细报告本身包含时间戳，这里主要是为了tg消息预览
        header = f"🔍 {timestamp} | {total_symbols}品种 | {count}共振 ✅"
        detail = format_resonance_report(resonances)
        return f"{header}\n{detail}"
    else:
        # 无共振：简短一行, 用咖啡杯表示休息
        return f"🔍 {timestamp} | {total_symbols}品种 | 0共振 | 垃圾时间 ☕"


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

    def notify(self, resonances: list[SymbolResonance]) -> None:
        """发送共振通知（只通知 5星 和 4星）"""
        msg = format_resonance_report(resonances)
        if not msg:
            return

        logger.info(msg)
        self._send(msg)

    def _send(self, message: str) -> None:
        """推送消息到 Telegram"""
        if not self.client or not self.token or not self.chat_id:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}

        try:
            resp = self.client.post(url, json=payload)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Telegram 推送失败: {e}")

    def close(self):
        """关闭 HTTP 客户端"""
        if self.client:
            self.client.close()
