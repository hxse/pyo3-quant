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
class OscillationStrategy(StrategyProtocol):
    """
    宽幅震荡策略 (Oscillation - Rust 引擎版)

    逻辑 (角色化级别版本):
    - MacroLevel: 震荡背景 (ADX弱 < 25)
    - TrendLevel: 震荡背景 (MACD走平 + 价格在EMA附近)
    - WaveLevel: 边界确认 (CCI由超买/超卖区域回弹)
    - TriggerLevel: 择机切入 (MACD零轴附近死叉/金叉)
    """

    name: Final[str] = "oscillation"

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
                "cci_h": {"period": Param(14)},
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
        # --- 震荡做多 (下轨反弹) ---
        long_filter = [
            # Macro: 趋势不强
            f"adx_w_adx,{dk_macro},0 < 30",
            # Trend: 动能走平
            f"macd_d_macd,{dk_trend},0 < 0.5",
            f"macd_d_macd,{dk_trend},0 > -0.5",
            # Wave: 超卖回弹
            f"cci_h,{dk_wave},1 < -100",
            f"cci_h,{dk_wave},0 > -100",
        ]

        # --- 震荡做空 (上轨回落) ---
        short_filter = [
            # Macro
            f"adx_w_adx,{dk_macro},0 < 30",
            # Trend
            f"macd_d_macd,{dk_trend},0 < 0.5",
            f"macd_d_macd,{dk_trend},0 > -0.5",
            # Wave: 超买回落
            f"cci_h,{dk_wave},1 > 100",
            f"cci_h,{dk_wave},0 < 100",
        ]

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=long_filter,
                sub_groups=[
                    SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[f"macd_m_hist,{dk_trigger},0 x> 0"],
                    )
                ],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=short_filter,
                sub_groups=[
                    SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[f"macd_m_hist,{dk_trigger},0 x< 0"],
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
        long_sig = signal_dict.get("entry_long", 0.0)
        short_sig = signal_dict.get("entry_short", 0.0)

        ts_str = format_timestamp(timestamp_ms)

        if long_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 震荡低位反弹",
                summary=f"{ctx.symbol} oscillation 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend低波动 + Wave超卖回归 + Trigger金叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 震荡高位回落",
                summary=f"{ctx.symbol} oscillation 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend低波动 + Wave超买回归 + Trigger死叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
