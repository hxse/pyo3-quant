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
class DebugSimpleStrategy(StrategyProtocol):
    """
    极简调试策略 (用于验证架构)
    逻辑：TriggerLevel 价格上穿 EMA20
    """

    name: Final[str] = "debug_simple"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        ctx.validate_levels_existence([ScanLevel.TRIGGER])

        # 获取数据键名
        dk_trigger = ctx.get_level_dk(ScanLevel.TRIGGER)

        # 1. 准备参数
        indicators = {
            dk_trigger: {
                "ema_test": {"period": Param.create(20)},
            },
        }

        # 2. 信号模板
        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"close,{dk_trigger},0 x> ema_test,{dk_trigger},0"],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[f"close,{dk_trigger},0 x< ema_test,{dk_trigger},0"],
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
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 均线金叉 (Debug)",
                summary=f"{ctx.symbol} debug 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    f"条件: {ctx.get_tf_name(ScanLevel.TRIGGER)} 价格突破 EMA20",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger=f"{ctx.get_tf_name(ScanLevel.TRIGGER)} 均线死叉 (Debug)",
                summary=f"{ctx.symbol} debug 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    f"条件: {ctx.get_tf_name(ScanLevel.TRIGGER)} 价格跌破 EMA20",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
