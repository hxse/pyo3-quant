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
class ReversalStrategy(StrategyProtocol):
    """
    逆势反转策略 (Reversal - Rust 引擎版)

    逻辑 (角色化级别版本):
    - MacroLevel: 极值区域 (ADX强 + CCI超买/超卖)
    - TrendLevel: 减速迹象 (MACD红柱缩短 / 蓝柱缩短 + 价格偏离EMA)
    - WaveLevel: 拐点显现 (MACD死叉/金叉)
    - TriggerLevel: 趋势反转 (价格穿越EMA + MACD柱确认)
    """

    name: Final[str] = "reversal"

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
                "cci_w": {"period": Param(14)},
                "adx_w": {"period": Param(14)},
            },
            dk_trend: {
                "macd_d": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
                "ema_d": {"period": Param(20)},
            },
            dk_wave: {
                "macd_h": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
            },
            dk_trigger: {
                "macd_m": {
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
                "ema_m": {"period": Param(20)},
            },
        }

        # 2. 信号逻辑
        # --- 摸底 (底部反转做多) ---
        long_filter = [
            # Macro: 极度超卖 + 趋势强劲 (准备反弹)
            f"cci_w,{dk_macro},0 < -150",
            f"adx_w_adx,{dk_macro},0 > 35",
            # Trend: 动能衰减
            f"macd_d_hist,{dk_trend},0 > macd_d_hist,{dk_trend},1",
            f"close,{dk_trend},0 < ema_d,{dk_trend},0",
            # Wave: 确立低点 (MACD转正/金叉)
            f"macd_h_hist,{dk_wave},0 > 0",
        ]

        # --- 摸顶 (顶部反转做空) ---
        short_filter = [
            # Macro: 极度超买
            f"cci_w,{dk_macro},0 > 150",
            f"adx_w_adx,{dk_macro},0 > 35",
            # Trend: 动能衰减
            f"macd_d_hist,{dk_trend},0 < macd_d_hist,{dk_trend},1",
            f"close,{dk_trend},0 > ema_d,{dk_trend},0",
            # Wave
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
            ],
        )

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=long_filter,
                sub_groups=[long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=short_filter,
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
        long_sig = signal_dict.get("entry_long", 0.0)
        short_sig = signal_dict.get("entry_short", 0.0)

        ts_str = format_timestamp(timestamp_ms)

        if long_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} V型反转启动",
                summary=f"{ctx.symbol} reversal 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro超卖 + Trend衰减 + Wave确认 + Trigger突破",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 顶部反转确认",
                summary=f"{ctx.symbol} reversal 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro超买 + Trend衰减 + Wave确认 + Trigger破位",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
