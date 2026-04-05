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
class MacdFallbackStrategy(StrategyBase):
    """
    MACD 分层方向策略

    方向判定（做多）：
    1. 若周线为零上红柱，则看多。
    2. 若周线中性，则继续读取日线；若日线为零上红柱，则看多。

    方向判定（做空）：
    1. 若周线为零下蓝柱，则看空。
    2. 若周线中性，则继续读取日线；若日线为零下蓝柱，则看空。

    中性判定：
    1. 若周线中性且日线仍中性，则整体观望。

    进场过滤：
    - 1h：做多允许红柱，或蓝柱衰减但快线仍在零上；做空允许蓝柱，或红柱衰减但快线仍在零下。

    进场触发：
    - 5m：MACD 翻色，或开盘第一根收盘站上/跌破 EMA20。
    """

    name: Final[str] = "macd_fallback_resonance"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 中文注释：该策略依赖 5m/1h/1d/1w 四层结构，周/日定方向，小时仅做过滤。
        required_levels = [
            ScanLevel.TRIGGER,
            ScanLevel.WAVE,
            ScanLevel.TREND,
            ScanLevel.MACRO,
        ]
        ctx.validate_levels_existence(required_levels)

        dk_trigger = ctx.get_level_dk(ScanLevel.TRIGGER)
        dk_wave = ctx.get_level_dk(ScanLevel.WAVE)
        dk_trend = ctx.get_level_dk(ScanLevel.TREND)
        dk_macro = ctx.get_level_dk(ScanLevel.MACRO)

        indicators = {
            dk_trigger: {
                "macd_m": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
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
            dk_macro: {
                "macd_w": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                }
            },
        }

        # 中文注释：周线/日线中性定义为“零轴方向与柱色不一致”，此时继续读取日线，否则直接观望。
        weekly_neutral_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_w_macd,{dk_macro},0 >= 0",
                        f"macd_w_hist,{dk_macro},0 <= 0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_w_macd,{dk_macro},0 <= 0",
                        f"macd_w_hist,{dk_macro},0 >= 0",
                    ],
                ),
            ],
        )

        # 中文注释：小时只做进场过滤，不参与方向定义；弱势衰减分支要求快线仍在零轴同侧。
        long_hour_filter_group = SignalGroup(
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
                        f"macd_h_macd,{dk_wave},0 > 0",
                    ],
                ),
            ],
        )

        short_hour_filter_group = SignalGroup(
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
                        f"macd_h_macd,{dk_wave},0 < 0",
                    ],
                ),
            ],
        )

        long_bias_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_w_macd,{dk_macro},0 > 0",
                        f"macd_w_hist,{dk_macro},0 > 0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_d_macd,{dk_trend},0 > 0",
                        f"macd_d_hist,{dk_trend},0 > 0",
                    ],
                    sub_groups=[weekly_neutral_group],
                ),
            ],
        )

        short_bias_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_w_macd,{dk_macro},0 < 0",
                        f"macd_w_hist,{dk_macro},0 < 0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_d_macd,{dk_trend},0 < 0",
                        f"macd_d_hist,{dk_trend},0 < 0",
                    ],
                    sub_groups=[weekly_neutral_group],
                ),
            ],
        )

        # 中文注释：5m 只负责执行时机，不负责定义大方向。
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
                        f"close,{dk_trigger},0 > close,{dk_trigger},1",
                    ],
                ),
            ],
        )

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
                        f"close,{dk_trigger},0 < close,{dk_trigger},1",
                    ],
                ),
            ],
        )

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                sub_groups=[
                    long_bias_group,
                    long_hour_filter_group,
                    long_trigger_group,
                ],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                sub_groups=[
                    short_bias_group,
                    short_hour_filter_group,
                    short_trigger_group,
                ],
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
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 多头触发",
                summary=f"{ctx.symbol} macd_fallback 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周线优先定多，周线中性退化到日线，小时仅做红柱或弱蓝衰减且零上过滤 + 5m 触发",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        if short_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 空头触发",
                summary=f"{ctx.symbol} macd_fallback 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周线优先定空，周线中性退化到日线，小时仅做蓝柱或弱红衰减且零下过滤 + 5m 触发",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
