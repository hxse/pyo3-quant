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
class TrendStrategy(StrategyProtocol):
    """
    强趋势共振策略 (Trend - Rust 引擎版)

    逻辑 (完全匹配 manual_trading.md 1.2):
    - 周线: CCI > 80 AND Close > EMA
    - 日线: CCI > 30 AND Close > EMA
    - 1小时: MACD红柱 AND Close > EMA
    - 5分钟: Close x> EMA (上穿) OR (开盘K线 AND Close > EMA) -- 单均线逻辑
    """

    name: Final[str] = "trend"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = ["5m", "1h", "1d", "1w"]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            "ohlcv_1w": {
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            "ohlcv_1d": {
                "cci_d": {"period": Param.create(14)},
                "ema_d": {"period": Param.create(20)},
            },
            "ohlcv_1h": {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_h": {"period": Param.create(20)},
            },
            "ohlcv_5m": {
                # 5分钟仅需 EMA20 和 开盘检测
                "ema_m": {"period": Param.create(20)},
                # 3600s = 60min = 1h, 即如果时间间隔 > 1小时则认为是开盘K线
                "opening-bar_0": {"threshold": Param.create(3600.0)},
            },
        }

        # 2. 信号逻辑
        # 文档结构: 大周期过滤 (AND) + 5m触发 (OR: 穿越 vs 开盘)

        # --- 共通的大周期过滤条件 ---
        long_filter = [
            # 周线
            "cci_w,ohlcv_1w,0 > 80",
            "close,ohlcv_1w,0 > ema_w,ohlcv_1w,0",
            # 日线
            "cci_d,ohlcv_1d,0 > 30",
            "close,ohlcv_1d,0 > ema_d,ohlcv_1d,0",
            # 1小时
            "macd_h_hist,ohlcv_1h,0 > 0",
            "close,ohlcv_1h,0 > ema_h,ohlcv_1h,0",
        ]

        short_filter = [
            # 周线 (做空对称)
            "cci_w,ohlcv_1w,0 < -80",
            "close,ohlcv_1w,0 < ema_w,ohlcv_1w,0",
            # 日线
            "cci_d,ohlcv_1d,0 < -30",
            "close,ohlcv_1d,0 < ema_d,ohlcv_1d,0",
            # 1小时
            "macd_h_hist,ohlcv_1h,0 < 0",
            "close,ohlcv_1h,0 < ema_h,ohlcv_1h,0",
        ]

        # --- 5m 触发条件 (OR) ---
        # 做多触发: 上穿 EMA 或者 (开盘 且 站上 EMA)
        long_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            comparisons=["close,ohlcv_5m,0 x> ema_m,ohlcv_5m,0"],
            sub_groups=[
                # 开盘且站上: opening > 0.5 AND close > ema
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "opening-bar_0,ohlcv_5m,0 > 0.5",
                        "close,ohlcv_5m,0 > ema_m,ohlcv_5m,0",
                    ],
                )
            ],
        )

        # 做空触发: 下穿 EMA 或者 (开盘 且 跌破 EMA)
        short_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            comparisons=["close,ohlcv_5m,0 x< ema_m,ohlcv_5m,0"],
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "opening-bar_0,ohlcv_5m,0 > 0.5",
                        "close,ohlcv_5m,0 < ema_m,ohlcv_5m,0",
                    ],
                )
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

        # 3. 转换数据
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

        # 4. 解析结果
        if not result.results:
            return None
        res_0 = result.results[0]
        if res_0.signals is None or res_0.signals.height == 0:
            return None

        last_row = res_0.signals.tail(1).to_dict(as_series=False)
        entry_signal = last_row["entry_long"][0]
        exit_signal = last_row["entry_short"][0]

        price = data.source["ohlcv_5m"].select(pl.col("close")).tail(1).item()

        if entry_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="Trend 突破进场",
                summary=f"{ctx.symbol} 强趋势共振突破",
                detail_lines=[
                    f"价格: {price}",
                    "条件: 周/日CCI强 + 1H红柱 + 5m突破/站稳EMA",
                ],
                metadata={"price": price},
            )

        if exit_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Trend 跌破进场",
                summary=f"{ctx.symbol} 强趋势共振跌破",
                detail_lines=[
                    f"价格: {price}",
                    "条件: 周/日CCI弱 + 1H绿柱 + 5m跌破/受阻EMA",
                ],
                metadata={"price": price},
            )

        return None
