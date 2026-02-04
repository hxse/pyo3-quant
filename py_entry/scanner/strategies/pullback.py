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
class PullbackStrategy(StrategyProtocol):
    """
    顺势回调策略 (Pullback / MeanReversion - Rust 引擎版)

    逻辑 (匹配 manual_trading.md 1.5):
    - 周线: 强趋势 (MACD同向 + 快线过零 + 价格在EMA同侧)
    - 日线: 次级折返 (MACD反向 + 但快线仍保持在零轴原侧 - 即弱反弹/回调)
    - 1小时: 折返结束 (MACD重回同向)
    - 5分钟: 刚刚触发 (MACD同向 + 刚刚穿越EMA)
    """

    name: Final[str] = "pullback"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = ["5m", "1h", "1d", "1w"]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            "ohlcv_1w": {
                "macd_w": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_w": {"period": Param.create(20)},
            },
            "ohlcv_1d": {
                "macd_d": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
            },
            "ohlcv_1h": {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
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
        # 5m 触发公式: (MACD同向 AND close x> EMA) OR (close > EMA AND MACD x> 0)

        # --- 做多逻辑 (周线强多 -> 日线弱回调 -> 1H回多 -> 5m启动) ---
        entry_comparisons = [
            # 1. [周线] 强多头
            "macd_w_hist,ohlcv_1w,0 > 0",  # 红柱
            "macd_w_macd,ohlcv_1w,0 > 0",  # 快线零上 (确保是多头趋势而非空头反弹)
            "close,ohlcv_1w,0 > ema_w,ohlcv_1w,0",  # 价格在均线上
            # 2. [日线] 次级回调 (红柱变蓝柱 / 或者是蓝柱)
            # 关键: 是回调而非反转 -> 快线必须还在零上!
            "macd_d_hist,ohlcv_1d,0 < 0",  # 蓝柱 (回调中)
            "macd_d_macd,ohlcv_1d,0 > 0",  # 但快线 > 0 (结构未坏)
            # 3. [1小时] 回调结束 (重回红柱)
            "macd_h_hist,ohlcv_1h,0 > 0",
            # 4. [5分钟] 刚刚触发 (OR逻辑)
            # 这里通过 SignalTemplate 将 Trigger 部分作为 sub_group 嵌入
            # 由于外层已经是 AND，我们在外层只写 1~3 的 AND
            # 第 4 部分由 long_trigger_group 处理
        ]

        # --- 做空逻辑 (周线强空 -> 日线弱反弹 -> 1H回空 -> 5m启动) ---
        exit_comparisons = [
            # 1. [周线] 强空头
            "macd_w_hist,ohlcv_1w,0 < 0",  # 蓝柱
            "macd_w_macd,ohlcv_1w,0 < 0",  # 快线零下
            "close,ohlcv_1w,0 < ema_w,ohlcv_1w,0",
            # 2. [日线] 次级反弹
            "macd_d_hist,ohlcv_1d,0 > 0",  # 红柱 (反弹中)
            "macd_d_macd,ohlcv_1d,0 < 0",  # 但快线 < 0 (结构未坏)
            # 3. [1小时] 反弹结束
            "macd_h_hist,ohlcv_1h,0 < 0",
        ]

        # 5m 做多触发 (OR)
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

        # 5m 做空触发 (OR)
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
                comparisons=entry_comparisons,
                sub_groups=[long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=exit_comparisons,
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
                trigger="Pullback 顺势回调买入",
                summary=f"{ctx.symbol} 强趋势回调结束",
                detail_lines=[f"价格: {price}", "条件: 周强多/日回调/1H回多/5m启动"],
                metadata=metadata,
            )

        if short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Pullback 顺势反弹做空",
                summary=f"{ctx.symbol} 强趋势反弹结束",
                detail_lines=[f"价格: {price}", "条件: 周强空/日反弹/1H回空/5m启动"],
                metadata=metadata,
            )

        return None
