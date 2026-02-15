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
class MomentumStrategy(StrategyProtocol):
    """
    爆发动量策略 (Momentum - Rust 引擎版)

    逻辑 (角色化级别版本):
    - MacroLevel: 动能转强 (MACD柱青转红 OR 红柱变长 + close > prev_close)
    - TrendLevel: 动能确认 (MACD红柱 + close > EMA)
    - WaveLevel: 动能确认 (MACD零上红柱)
    - TriggerLevel: 价格突破 (MACD零上金叉/转红)
    """

    name: Final[str] = "momentum"

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
                    "fast_period": Param(12),
                    "slow_period": Param(26),
                    "signal_period": Param(9),
                },
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
            },
        }

        # 2. 信号逻辑
        # --- 做多逻辑 ---
        long_filter = [
            # Macro: 动能转强 (逻辑稍复杂，这里简化为红柱且收阳)
            f"macd_w_hist,{dk_macro},0 > 0",
            f"close,{dk_macro},0 > close,{dk_macro},1",
            # Trend
            f"macd_d_hist,{dk_trend},0 > 0",
            f"close,{dk_trend},0 > ema_d,{dk_trend},0",
            # Wave
            f"macd_h_hist,{dk_wave},0 > 0",
            f"macd_h_macd,{dk_wave},0 > 0",
        ]

        # --- 做空逻辑 ---
        short_filter = [
            # Macro
            f"macd_w_hist,{dk_macro},0 < 0",
            f"close,{dk_macro},0 < close,{dk_macro},1",
            # Trend
            f"macd_d_hist,{dk_trend},0 < 0",
            f"close,{dk_trend},0 < ema_d,{dk_trend},0",
            # Wave
            f"macd_h_hist,{dk_wave},0 < 0",
            f"macd_h_macd,{dk_wave},0 < 0",
        ]

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=long_filter,
                sub_groups=[
                    SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[
                            f"macd_m_macd,{dk_trigger},0 > 0",
                            f"macd_m_hist,{dk_trigger},0 x> 0",
                        ],
                    )
                ],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=short_filter,
                sub_groups=[
                    SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[
                            f"macd_m_macd,{dk_trigger},0 < 0",
                            f"macd_m_hist,{dk_trigger},0 x< 0",
                        ],
                    )
                ],
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
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} MACD动量爆发",
                summary=f"{ctx.symbol} momentum 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend/Wave 动能共振 + Trigger起爆",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} MACD动量下杀",
                summary=f"{ctx.symbol} momentum 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend/Wave 动能衰减 + Trigger破位",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
