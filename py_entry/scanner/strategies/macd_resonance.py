from typing import Final

from py_entry.scanner.config import ScanLevel
from py_entry.scanner.strategies.base import (
    ScanContext,
    StrategyBase,
    StrategySignal,
    format_timestamp,
    run_scan_backtest,
)
from py_entry.scanner.strategies.registry import StrategyRegistry
from py_entry.types import LogicOp, Param, SignalGroup, SignalTemplate


@StrategyRegistry.register
class MacdResonanceStrategy(StrategyBase):
    """
    MACD 三周期共振策略（5m / 1h / 1d）

    做多:
    - Trigger(5m): MACD 柱蓝转红 (x> 0)
    - Wave(1h): MACD 红柱，或者蓝柱衰减（当前蓝柱比上一根更短）
    - Trend(1d): MACD 红柱

    做空（严格镜像）:
    - Trigger(5m): MACD 柱红转蓝 (x< 0)
    - Wave(1h): MACD 蓝柱，或者红柱衰减（当前红柱比上一根更短）
    - Trend(1d): MACD 蓝柱
    """

    name: Final[str] = "macd_5m_1h_1d_resonance"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 中文注释：该策略仅依赖 5m/1h/1d 三个层级，不依赖 macro。
        required_levels = [ScanLevel.TRIGGER, ScanLevel.WAVE, ScanLevel.TREND]
        ctx.validate_levels_existence(required_levels)

        dk_trigger = ctx.get_level_dk(ScanLevel.TRIGGER)
        dk_wave = ctx.get_level_dk(ScanLevel.WAVE)
        dk_trend = ctx.get_level_dk(ScanLevel.TREND)

        indicators = {
            dk_trigger: {
                "macd_m": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
                # 中文注释：增加 5m EMA 与开盘第一根检测，用于补充开盘触发条件。
                "ema_m": {"period": Param(20)},
                "opening-bar_0": {"threshold": Param(3600.0)},
            },
            dk_wave: {
                "macd_h": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                }
            },
            dk_trend: {
                "macd_d": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                }
            },
        }

        # 中文注释：小时条件用 OR 组表达“红柱 或 蓝柱衰减”。
        long_hour_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"macd_h_hist,{dk_wave},0 > 0"],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_h_hist,{dk_wave},0 < 0",
                        f"macd_h_hist,{dk_wave},0 > macd_h_hist,{dk_wave},1",
                    ],
                ),
            ],
        )

        # 中文注释：空头小时条件镜像“蓝柱 或 红柱衰减”。
        short_hour_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"macd_h_hist,{dk_wave},0 < 0"],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_h_hist,{dk_wave},0 > 0",
                        f"macd_h_hist,{dk_wave},0 < macd_h_hist,{dk_wave},1",
                    ],
                ),
            ],
        )

        # 中文注释：5m 触发增加“开盘第一根 + 站上/跌破 EMA”条件，与 MACD 穿越做 OR。
        long_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"macd_m_hist,{dk_trigger},0 x> 0"],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"opening-bar_0,{dk_trigger},0 > 0.5",
                        f"close,{dk_trigger},0 > ema_m,{dk_trigger},0",
                        # 中文注释：开盘场景要求当前收盘价继续走强（高于上一根收盘）。
                        f"close,{dk_trigger},0 > close,{dk_trigger},1",
                    ],
                ),
            ],
        )

        # 中文注释：空头触发严格镜像多头触发逻辑。
        short_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"macd_m_hist,{dk_trigger},0 x< 0"],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"opening-bar_0,{dk_trigger},0 > 0.5",
                        f"close,{dk_trigger},0 < ema_m,{dk_trigger},0",
                        # 中文注释：空头开盘场景要求当前收盘价继续走弱（低于上一根收盘）。
                        f"close,{dk_trigger},0 < close,{dk_trigger},1",
                    ],
                ),
            ],
        )

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"macd_d_hist,{dk_trend},0 > 0"],
                sub_groups=[long_hour_group, long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"macd_d_hist,{dk_trend},0 < 0"],
                sub_groups=[short_hour_group, short_trigger_group],
            ),
        )

        result = run_scan_backtest(
            ctx=ctx,
            indicators=indicators,
            signal_template=template,
            base_level=ScanLevel.TRIGGER,
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        long_signal = signal_dict.get("entry_long", 0.0)
        short_signal = signal_dict.get("entry_short", 0.0)
        ts_str = format_timestamp(timestamp_ms)

        if long_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} MACD 蓝转红",
                summary=f"{ctx.symbol} macd_resonance 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 1d 红柱 + 1h 红柱或蓝柱衰减 + 5m(MACD蓝转红 或 开盘首根站上EMA)",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        if short_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} MACD 红转蓝",
                summary=f"{ctx.symbol} macd_resonance 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 1d 蓝柱 + 1h 蓝柱或红柱衰减 + 5m(MACD红转蓝 或 开盘首根跌破EMA)",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
