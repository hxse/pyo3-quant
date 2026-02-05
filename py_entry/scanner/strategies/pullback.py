from typing import Final
from py_entry.scanner.config import ScanLevel
from py_entry.scanner.strategies.base import (
    StrategyProtocol,
    ScanContext,
    StrategySignal,
    run_scan_backtest,
    format_timestamp,
)
from py_entry.scanner.strategies.registry import StrategyRegistry
from py_entry.types import (
    SignalTemplate,
    Param,
    SignalGroup,
    LogicOp,
)


@StrategyRegistry.register
class PullbackStrategy(StrategyProtocol):
    """
    顺势回调策略 (Pullback / MeanReversion - Rust 引擎版)

    逻辑 (角色化级别版本):
    - MacroLevel: 强趋势 (MACD同向 + 快线过零 + 价格在EMA同侧)
    - TrendLevel: 次级折返 (MACD反向 + 且快线仍保持在零轴原侧)
    - WaveLevel: 折返结束 (MACD重回同向)
    - TriggerLevel: 刚刚触发 (MACD同向 + 刚刚穿越EMA)
    """

    name: Final[str] = "pullback"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_levels = [
            ScanLevel.TRIGGER,
            ScanLevel.WAVE,
            ScanLevel.TREND,
            ScanLevel.MACRO,
        ]
        ctx.validate_levels_existence(required_levels)

        # 获取数据键名
        dk_macro = ctx.get_level_dk(ScanLevel.MACRO)
        dk_trend = ctx.get_level_dk(ScanLevel.TREND)
        dk_wave = ctx.get_level_dk(ScanLevel.WAVE)
        dk_trigger = ctx.get_level_dk(ScanLevel.TRIGGER)

        # 1. 准备参数
        indicators = {
            dk_macro: {
                "macd_w": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_w": {"period": Param.create(20)},
            },
            dk_trend: {
                "macd_d": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
            },
            dk_wave: {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
            },
            dk_trigger: {
                "macd_m": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_m": {"period": Param.create(20)},
            },
        }

        # 2. 信号逻辑 (Rust 表达式)
        # --- 做多逻辑 ---
        entry_comparisons = [
            # 1. [Macro] 强多头
            f"macd_w_hist,{dk_macro},0 > 0",
            f"macd_w_macd,{dk_macro},0 > 0",
            f"close,{dk_macro},0 > ema_w,{dk_macro},0",
            # 2. [Trend] 次级回调 (红柱变蓝柱 / 或者是蓝柱)
            f"macd_d_hist,{dk_trend},0 < 0",
            f"macd_d_macd,{dk_trend},0 > 0",
            # 3. [Wave] 回调结束 (重回红柱)
            f"macd_h_hist,{dk_wave},0 > 0",
        ]

        # --- 做空逻辑 ---
        exit_comparisons = [
            # 1. [Macro] 强空头
            f"macd_w_hist,{dk_macro},0 < 0",
            f"macd_w_macd,{dk_macro},0 < 0",
            f"close,{dk_macro},0 < ema_w,{dk_macro},0",
            # 2. [Trend] 次级反弹
            f"macd_d_hist,{dk_trend},0 > 0",
            f"macd_d_macd,{dk_trend},0 < 0",
            # 3. [Wave] 反弹结束
            f"macd_h_hist,{dk_wave},0 < 0",
        ]

        # Trigger 做多触发 (OR)
        long_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_m_hist,{dk_trigger},0 > 0",
                        f"close,{dk_trigger},0 x> ema_m,{dk_trigger},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"close,{dk_trigger},0 > ema_m,{dk_trigger},0",
                        f"macd_m_hist,{dk_trigger},0 x> 0",
                    ],
                ),
            ],
        )

        # Trigger 做空触发 (OR)
        short_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_m_hist,{dk_trigger},0 < 0",
                        f"close,{dk_trigger},0 x< ema_m,{dk_trigger},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"close,{dk_trigger},0 < ema_m,{dk_trigger},0",
                        f"macd_m_hist,{dk_trigger},0 x< 0",
                    ],
                ),
            ],
        )

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=entry_comparisons,
                sub_groups=[long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=exit_comparisons,
                sub_groups=[short_trigger_group],
            ),
        )

        # 3. 运行回测
        result = run_scan_backtest(
            ctx=ctx,
            indicators=indicators,
            signal_template=template,
            base_level=ScanLevel.TRIGGER,
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        entry_sig = signal_dict.get("entry_long", 0.0)
        short_sig = signal_dict.get("entry_short", 0.0)

        ts_str = format_timestamp(timestamp_ms)

        if entry_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 趋势回调启动",
                summary=f"{ctx.symbol} pullback 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend共振 + Wave转多 + Trigger穿越",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 趋势反弹启动",
                summary=f"{ctx.symbol} pullback 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend共振 + Wave转空 + Trigger穿越",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
