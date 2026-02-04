from typing import Final
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
class DebugSimpleResonanceStrategy(StrategyProtocol):
    """
    Debug 专用简易双周期共振策略
    - 5m: 价格站在 EMA 20 之上/下 (趋势)
    - 1h: MACD 柱状图 > 0 / < 0 (动能)
    """

    name: Final[str] = "debug_simple"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 1. 验证所需周期
        required_tfs = ["5m", "1h"]
        ctx.validate_klines_existence(required_tfs)

        # 2. 定义指标参数
        indicators = {
            "ohlcv_1h": {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
            "ohlcv_5m": {
                "ema_m": {"period": Param.create(20)},
            },
        }

        # 3. 信号逻辑 (Rust 表达式)
        # 做多: 1h MACD 红柱 + 5m 价格金叉 EMA
        entry_long = [
            "macd_h_hist,ohlcv_1h,0 > 0",
            "close,ohlcv_5m,0 x> ema_m,ohlcv_5m,0",
        ]

        # 做空: 1h MACD 绿柱 + 5m 价格死叉 EMA
        entry_short = [
            "macd_h_hist,ohlcv_1h,0 < 0",
            "close,ohlcv_5m,0 x< ema_m,ohlcv_5m,0",
        ]

        template = SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=entry_long),
            entry_short=SignalGroup(logic=LogicOp.AND, comparisons=entry_short),
        )

        # 4. 运行回测 (使用 helper)
        result = run_scan_backtest(
            ctx=ctx,
            indicators=indicators,
            signal_template=template,
            base_tf="ohlcv_5m",
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        is_long = signal_dict.get("entry_long", 0.0) > 0.5
        is_short = signal_dict.get("entry_short", 0.0) > 0.5

        # 格式化时间
        ts_str = format_timestamp(timestamp_ms)

        if is_long:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="Debug Long",
                summary=f"{ctx.symbol} - debug 信号触发",
                detail_lines=[f"时间: {ts_str}", f"Triggered at price: {price}"],
                metadata={"price": price, "time": timestamp_ms},
            )

        if is_short:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Debug Short",
                summary=f"{ctx.symbol} - debug 做空触发",
                detail_lines=[f"时间: {ts_str}", f"Triggered at price: {price}"],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
