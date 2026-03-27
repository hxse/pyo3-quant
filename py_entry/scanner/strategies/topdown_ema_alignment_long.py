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
class TopdownEmaAlignmentLongStrategy(StrategyBase):
    """
    自上而下 EMA 结构多头扫描策略

    方向条件：
    1. 5m close > 1d EMA20 > 1d EMA50；
    2. 或 5m close > 1w EMA20 > 1w EMA50。

    小时过滤：
    1. 1h EMA20 > EMA50；
    2. 1h close > EMA50。

    5m 触发：
    1. 5m EMA20 > EMA50；
    2. 且 5m close 上穿 EMA20，或开盘第一根 5m K 线直接站上 EMA20。

    设计约束：
    1. 仅实现用户明确给出的多头口径；
    2. 不额外补空头镜像逻辑。
    """

    name: Final[str] = "topdown_ema_alignment_long"
    OPENING_BAR_THRESHOLD_SECONDS: Final[float] = 3600.0

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 中文注释：该策略固定使用 5m / 1h / 1d / 1w 四层结构。
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
                "ema_m_fast": {"period": Param(20)},
                "ema_m_slow": {"period": Param(50)},
                "opening-bar_0": {
                    "threshold": Param(self.OPENING_BAR_THRESHOLD_SECONDS)
                },
            },
            dk_wave: {
                "ema_h_fast": {"period": Param(20)},
                "ema_h_slow": {"period": Param(50)},
            },
            dk_trend: {
                "ema_d_fast": {"period": Param(20)},
                "ema_d_slow": {"period": Param(50)},
            },
            dk_macro: {
                "ema_w_fast": {"period": Param(20)},
                "ema_w_slow": {"period": Param(50)},
            },
        }

        daily_bias_group = SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"close,{dk_trigger},0 > ema_d_fast,{dk_trend},0",
                f"ema_d_fast,{dk_trend},0 > ema_d_slow,{dk_trend},0",
            ],
        )
        weekly_bias_group = SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"close,{dk_trigger},0 > ema_w_fast,{dk_macro},0",
                f"ema_w_fast,{dk_macro},0 > ema_w_slow,{dk_macro},0",
            ],
        )

        higher_bias_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[daily_bias_group, weekly_bias_group],
        )

        hour_filter_group = SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"ema_h_fast,{dk_wave},0 > ema_h_slow,{dk_wave},0",
                f"close,{dk_wave},0 > ema_h_slow,{dk_wave},0",
            ],
        )

        entry_timing_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"close,{dk_trigger},0 x> ema_m_fast,{dk_trigger},0"],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"opening-bar_0,{dk_trigger},0 > 0.5",
                        f"close,{dk_trigger},0 > ema_m_fast,{dk_trigger},0",
                    ],
                ),
            ],
        )

        trigger_group = SignalGroup(
            logic=LogicOp.AND,
            comparisons=[f"ema_m_fast,{dk_trigger},0 > ema_m_slow,{dk_trigger},0"],
            sub_groups=[entry_timing_group],
        )

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                sub_groups=[
                    higher_bias_group,
                    hour_filter_group,
                    trigger_group,
                ],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                # 中文注释：策略只输出多头机会，这里保留统一模板所需占位条件。
                comparisons=[f"close,{dk_trigger},0 < 0"],
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
        if long_signal <= 0.5:
            return None

        ts_str = format_timestamp(timestamp_ms)
        return StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            direction="long",
            trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 多头触发",
            summary=f"{ctx.symbol} EMA alignment 做多",
            detail_lines=[
                f"时间: {ts_str}",
                f"价格: {price}",
                "条件: (5m > 1d EMA20 > EMA50 或 5m > 1w EMA20 > EMA50) + 1h EMA20 > EMA50 且 close > EMA50 + 5m EMA20 > EMA50 后上穿/开盘首根站上 EMA20",
            ],
            metadata={"price": price, "time": timestamp_ms},
        )
