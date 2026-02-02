import unittest
from typing import Literal
from py_entry.scanner.notifier import format_signal_report, format_heartbeat
from py_entry.scanner.strategies.base import StrategySignal


def make_signal(
    symbol: str,
    direction: Literal["long", "short", "none"] = "long",
    warnings: list[str] | None = None,
) -> StrategySignal:
    return StrategySignal(
        strategy_name="trend",
        symbol=symbol,
        direction=direction,
        trigger="5m上穿EMA",
        summary=f"{symbol} 做多",
        detail_lines=["[5m] 上穿EMA", "[1h] MACD红"],
        warnings=warnings or [],
    )


class TestNotifier(unittest.TestCase):
    def test_format_signal_report_empty(self):
        self.assertEqual(format_signal_report([]), "")

    def test_format_signal_report_single(self):
        report = format_signal_report([make_signal("SHFE.rb")])
        self.assertIn("SHFE.rb", report)
        self.assertIn("trend", report)
        self.assertIn("做多", report)

    def test_format_signal_report_with_warnings(self):
        sig = make_signal("SHFE.rb", warnings=["⚠️ ER走弱"])
        report = format_signal_report([sig])
        self.assertIn("⚠️", report)
        self.assertIn("ER走弱", report)

    def test_format_heartbeat_no_signals(self):
        msg = format_heartbeat(20, [])
        self.assertIn("0信号", msg)
        self.assertIn("垃圾时间", msg)

    def test_format_heartbeat_with_signals(self):
        msg = format_heartbeat(20, [make_signal("A")])
        self.assertIn("1信号", msg)
        self.assertIn("✅", msg)
        self.assertIn("trend", msg)
