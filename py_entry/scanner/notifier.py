"""通知器 - 日志打印 + 可扩展推送"""

import logging
from datetime import datetime
from .resonance import SymbolResonance, ResonanceLevel

logger = logging.getLogger("scanner")


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
        # 过滤掉垃圾等级
        valid = [r for r in resonances if r.level != ResonanceLevel.GARBAGE]

        if not valid:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in valid:
            stars = "⭐" * r.level.value
            direction = "📈做多" if r.direction == "long" else "📉做空"

            # 构建详情字符串
            details_str = "\n".join(
                [f"  - {t.timeframe}: {t.detail}" for t in r.timeframes]
            )

            msg = f"""
[{timestamp}] {stars} 共振信号
品种: {r.symbol}
方向: {direction}
触发: {r.trigger_signal}
详情:
{details_str}
            """
            logger.info(msg.strip())
            self._send(msg.strip())

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
