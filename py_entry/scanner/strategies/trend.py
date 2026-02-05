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
class TrendStrategy(StrategyProtocol):
    """
    强趋势共振策略 (Trend - Rust 引擎版)

    逻辑 (角色化级别版本):
    - MacroLevel: CCI > 80 AND Close > EMA
    - TrendLevel: CCI > 30 AND Close > EMA
    - WaveLevel: MACD红柱 AND Close > EMA
    - TriggerLevel: (MACD红柱 AND close x> EMA) OR (close > EMA AND MACD红柱上穿0)
    """

    name: Final[str] = "trend"

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
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            dk_trend: {
                "cci_d": {"period": Param.create(14)},
                "ema_d": {"period": Param.create(20)},
            },
            dk_wave: {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_h": {"period": Param.create(20)},
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

        # 2. 信号逻辑
        # 文档结构: 大周期过滤 (AND) + 15m触发 (OR: 穿越 vs 开盘)

        # --- 共通的大周期过滤条件 ---
        long_filter = [
            # Macro
            f"cci_w,{dk_macro},0 > 80",
            f"close,{dk_macro},0 > ema_w,{dk_macro},0",
            # Trend
            f"cci_d,{dk_trend},0 > 30",
            f"close,{dk_trend},0 > ema_d,{dk_trend},0",
            # Wave
            f"macd_h_hist,{dk_wave},0 > 0",
            f"close,{dk_wave},0 > ema_h,{dk_wave},0",
        ]

        short_filter = [
            # Macro (做空对称)
            f"cci_w,{dk_macro},0 < -80",
            f"close,{dk_macro},0 < ema_w,{dk_macro},0",
            # Trend
            f"cci_d,{dk_trend},0 < -30",
            f"close,{dk_trend},0 < ema_d,{dk_trend},0",
            # Wave
            f"macd_h_hist,{dk_wave},0 < 0",
            f"close,{dk_wave},0 < ema_h,{dk_wave},0",
        ]

        # --- Trigger 触发条件 (OR) ---
        # 做多触发: (MACD红柱 AND 上穿EMA) OR (站上EMA AND MACD金叉/转红)
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

        # 做空触发: 对称逻辑
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
                comparisons=long_filter,
                sub_groups=[long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=short_filter,
                sub_groups=[short_trigger_group],
            ),
        )

        # 3. 运行回测 (使用 helper)
        result = run_scan_backtest(
            ctx=ctx,
            indicators=indicators,
            signal_template=template,
            base_level=ScanLevel.TRIGGER,
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        entry_signal = signal_dict.get("entry_long", 0.0)
        exit_signal = signal_dict.get("entry_short", 0.0)

        # 格式化时间
        ts_str = format_timestamp(timestamp_ms)

        if entry_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 突破进场",
                summary=f"{ctx.symbol} trend 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend CCI强 + Wave红柱 + Trigger红柱/突破EMA共振",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif exit_signal > 0.5:
            # 注意：Trend 策略目前只定义了 Entry Long，Exit Short 暂未完全对齐
            # 但为了对称性，这里保留处理，或者根据实际需求修改
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 向下突破",
                summary=f"{ctx.symbol} trend 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: Macro/Trend CCI弱 + Wave绿柱 + Trigger绿柱/跌破EMA共振",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
