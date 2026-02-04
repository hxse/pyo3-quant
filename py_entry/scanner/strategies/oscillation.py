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
class OscillationStrategy(StrategyProtocol):
    """
    震荡回归策略 (Oscillation Reversion - Rust 引擎版)

    逻辑 (匹配 manual_trading.md 1.6):
    - 周线: 中枢震荡 (40 < RSI < 60)
    - 日线: 中枢震荡 (40 < RSI < 60)
    - 1小时: 超卖/超买 (RSI < 35 / RSI > 65)
    - 5分钟: 企稳/见顶 (MACD红柱+站上EMA / MACD绿柱+跌破EMA)
    """

    name: Final[str] = "oscillation"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = ["5m", "1h", "1d", "1w"]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            "ohlcv_1w": {
                "rsi_w": {"period": Param.create(14)},
            },
            "ohlcv_1d": {
                "rsi_d": {"period": Param.create(14)},
            },
            "ohlcv_1h": {
                "rsi_h": {"period": Param.create(14)},
            },
            "ohlcv_5m": {
                "macd_m": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_m": {"period": Param.create(20)},
            },
        }

        # 2. 信号逻辑 (Rust 表达式)
        # 核心定义: 刚刚触发 = (当前满足组合) AND (上一刻不同时满足)
        # 等价于: (MACD红 且 价格上穿EMA) OR (价格在EMA上 且 MACD翻红)

        # --- 共通的大周期过滤 ---
        long_filter = [
            "rsi_w,ohlcv_1w,0 > 40",
            "rsi_w,ohlcv_1w,0 < 60",  # 周线中枢
            "rsi_d,ohlcv_1d,0 > 40",
            "rsi_d,ohlcv_1d,0 < 60",  # 日线中枢
            "rsi_h,ohlcv_1h,0 < 35",  # 1H 超卖
        ]

        short_filter = [
            "rsi_w,ohlcv_1w,0 > 40",
            "rsi_w,ohlcv_1w,0 < 60",
            "rsi_d,ohlcv_1d,0 > 40",
            "rsi_d,ohlcv_1d,0 < 60",
            "rsi_h,ohlcv_1h,0 > 65",  # 1H 超买
        ]

        # --- 5m 触发条件 (OR) ---

        # 做多触发
        long_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                # 路径1: 动能已备，价格突破
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "macd_m_hist,ohlcv_5m,0 > 0",
                        "close,ohlcv_5m,0 x> ema_m,ohlcv_5m,0",
                    ],
                ),
                # 路径2: 价格已备，动能起爆
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "close,ohlcv_5m,0 > ema_m,ohlcv_5m,0",
                        "macd_m_hist,ohlcv_5m,0 x> 0",
                    ],
                ),
            ],
        )

        # 做空触发
        short_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                # 路径1: 动能已弱，价格跌破
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "macd_m_hist,ohlcv_5m,0 < 0",
                        "close,ohlcv_5m,0 x< ema_m,ohlcv_5m,0",
                    ],
                ),
                # 路径2: 价格已破，动能翻绿
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "close,ohlcv_5m,0 < ema_m,ohlcv_5m,0",
                        "macd_m_hist,ohlcv_5m,0 x< 0",
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

        # 3. 计算
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
        entry_sig = last_row["entry_long"][0]
        short_sig = last_row["entry_short"][0]

        price = data.source["ohlcv_5m"].select(pl.col("close")).tail(1).item()
        metadata = {"price": price}

        if entry_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="Oscillation 超卖反弹",
                summary=f"{ctx.symbol} 震荡区间超卖反弹",
                detail_lines=[f"价格: {price}", "条件: 周日RSI中枢 + 1H超卖 + 5m企稳"],
                metadata=metadata,
            )

        if short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Oscillation 超买回落",
                summary=f"{ctx.symbol} 震荡区间超买回落",
                detail_lines=[f"价格: {price}", "条件: 周日RSI中枢 + 1H超买 + 5m见顶"],
                metadata=metadata,
            )

        return None
