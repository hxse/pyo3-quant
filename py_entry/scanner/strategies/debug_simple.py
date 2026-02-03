from typing import Final
from py_entry.scanner.strategies.base import (
    StrategyProtocol,
    ScanContext,
    StrategySignal,
)
from py_entry.scanner.strategies.registry import StrategyRegistry
from py_entry.runner import Backtest
from py_entry.data_generator import DirectDataConfig
from py_entry.types import (
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
    Param,
    SignalGroup,
    LogicOp,
    BacktestParams,
    PerformanceParams,
)
import polars as pl


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

        # 4. 运行回测扫描
        data = ctx.to_data_container(base_tf="ohlcv_5m")

        settings = SettingContainer(
            execution_stage=ExecutionStage.SIGNALS,
            return_only_final=False,
        )

        bt = Backtest(
            data_source=DirectDataConfig(
                data=data.source, base_data_key=data.base_data_key
            ),
            indicators=indicators,
            signal_template=template,
            engine_settings=settings,
            backtest=BacktestParams(
                initial_capital=10000.0,
                fee_fixed=1.0,
                fee_pct=0.0005,
            ),
            performance=PerformanceParams(metrics=[]),
        )

        result = bt.run()

        # 5. 解析结果
        if not result.results:
            return None
        res_0 = result.results[0]
        if res_0.signals is None or res_0.signals.height == 0:
            return None

        last_row = res_0.signals.tail(1).to_dict(as_series=False)
        is_long = last_row["entry_long"][0] > 0.5
        is_short = last_row["entry_short"][0] > 0.5

        price = data.source["ohlcv_5m"].select(pl.col("close")).tail(1).item()

        if is_long:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="1h-MACD(+) & 5m-EMA-XOver",
                summary=f"{ctx.symbol} [DEBUG] 5m金叉 + 1h红柱",
                detail_lines=["价格: {price}", "周期: 5m, 1h"],
                metadata={"price": price},
            )

        if is_short:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="1h-MACD(-) & 5m-EMA-XUnder",
                summary=f"{ctx.symbol} [DEBUG] 5m死叉 + 1h绿柱",
                detail_lines=["价格: {price}", "周期: 5m, 1h"],
                metadata={"price": price},
            )

        return None
