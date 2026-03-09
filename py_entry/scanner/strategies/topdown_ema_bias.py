from typing import Final

from py_entry.scanner.config import ScanLevel
from py_entry.scanner.strategies.base import (
    ScanContext,
    StrategyProtocol,
    StrategySignal,
    format_timestamp,
    run_scan_backtest,
)
from py_entry.scanner.strategies.registry import StrategyRegistry
from py_entry.types import LogicOp, Param, SignalGroup, SignalTemplate


@StrategyRegistry.register
class TopdownEmaBiasStrategy(StrategyProtocol):
    """
    周/日方向优先 + 小时动量 + 5m 触发策略

    多头方向判定：
    1. 若 5m 已完成 K 线 low > 1w EMA20 且 low > 1w EMA60，则只做多。
    2. 若周线方向不明朗，则退化为用 5m low 与 1d EMA20/60 对比；若二者都在下方，则只做多。

    空头方向判定：
    1. 若 5m 已完成 K 线 high < 1w EMA20 且 high < 1w EMA60，则只做空。
    2. 若周线方向不明朗，则退化为用 5m high 与 1d EMA20/60 对比；若二者都在上方，则只做空。

    进场触发沿用现有扫描器风格：
    - 1h：MACD 同向，或反向柱衰减
    - 5m：MACD 翻色，或开盘第一根收盘站上/跌破 EMA20
    """

    name: Final[str] = "topdown_ema_bias_resonance"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 中文注释：该策略同时依赖 5m/1h/1d/1w 四个层级。
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
                "ema_fast": {"period": Param(20)},
                "ema_slow": {"period": Param(60)},
            },
            dk_macro: {
                "ema_w_20": {"period": Param(20)},
                "ema_w_60": {"period": Param(60)},
            },
        }

        weekly_mixed_group = SignalGroup(
            logic=LogicOp.AND,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.OR,
                    comparisons=[
                        f"low,{dk_trigger},0 <= ema_w_20,{dk_macro},0",
                        f"low,{dk_trigger},0 <= ema_w_60,{dk_macro},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.OR,
                    comparisons=[
                        f"high,{dk_trigger},0 >= ema_w_20,{dk_macro},0",
                        f"high,{dk_trigger},0 >= ema_w_60,{dk_macro},0",
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
                        f"low,{dk_trigger},0 > ema_w_20,{dk_macro},0",
                        f"low,{dk_trigger},0 > ema_w_60,{dk_macro},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"low,{dk_trigger},0 > ema_fast,{dk_trend},0",
                        f"low,{dk_trigger},0 > ema_slow,{dk_trend},0",
                    ],
                    sub_groups=[weekly_mixed_group],
                ),
            ],
        )

        short_bias_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"high,{dk_trigger},0 < ema_w_20,{dk_macro},0",
                        f"high,{dk_trigger},0 < ema_w_60,{dk_macro},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"high,{dk_trigger},0 < ema_fast,{dk_trend},0",
                        f"high,{dk_trigger},0 < ema_slow,{dk_trend},0",
                    ],
                    sub_groups=[weekly_mixed_group],
                ),
            ],
        )

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
                sub_groups=[long_bias_group, long_hour_group, long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                sub_groups=[short_bias_group, short_hour_group, short_trigger_group],
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
                summary=f"{ctx.symbol} topdown_ema_bias 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周线优先定多，周线不明朗则日线定多 + 1h 红柱/蓝衰减 + 5m 翻红/开盘首根站上 EMA",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        if short_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 空头触发",
                summary=f"{ctx.symbol} topdown_ema_bias 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周线优先定空，周线不明朗则日线定空 + 1h 蓝柱/红衰减 + 5m 翻蓝/开盘首根跌破 EMA",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
