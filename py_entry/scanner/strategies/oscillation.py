from typing import Final
from py_entry.scanner.config import (
    TF_5M,
    TF_1H,
    TF_1D,
    TF_1W,
    DK_5M,
    DK_1H,
    DK_1D,
    DK_1W,
)
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
        required_tfs = [TF_5M, TF_1H, TF_1D, TF_1W]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            DK_1W: {
                "rsi_w": {"period": Param.create(14)},
            },
            DK_1D: {
                "rsi_d": {"period": Param.create(14)},
            },
            DK_1H: {
                "rsi_h": {"period": Param.create(14)},
            },
            DK_5M: {
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
            f"rsi_w,{DK_1W},0 > 40",
            f"rsi_w,{DK_1W},0 < 60",  # 周线中枢
            f"rsi_d,{DK_1D},0 > 40",
            f"rsi_d,{DK_1D},0 < 60",  # 日线中枢
            f"rsi_h,{DK_1H},0 < 35",  # 1H 超卖
        ]

        short_filter = [
            f"rsi_w,{DK_1W},0 > 40",
            f"rsi_w,{DK_1W},0 < 60",
            f"rsi_d,{DK_1D},0 > 40",
            f"rsi_d,{DK_1D},0 < 60",
            f"rsi_h,{DK_1H},0 > 65",  # 1H 超买
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
                        f"macd_m_hist,{DK_5M},0 > 0",
                        f"close,{DK_5M},0 x> ema_m,{DK_5M},0",
                    ],
                ),
                # 路径2: 价格已备，动能起爆
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"close,{DK_5M},0 > ema_m,{DK_5M},0",
                        f"macd_m_hist,{DK_5M},0 x> 0",
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
                        f"macd_m_hist,{DK_5M},0 < 0",
                        f"close,{DK_5M},0 x< ema_m,{DK_5M},0",
                    ],
                ),
                # 路径2: 价格已破，动能翻绿
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"close,{DK_5M},0 < ema_m,{DK_5M},0",
                        f"macd_m_hist,{DK_5M},0 x< 0",
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
            base_tf=DK_5M,
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        entry_sig = signal_dict.get("entry_long", 0.0)
        short_sig = signal_dict.get("entry_short", 0.0)

        # 格式化时间
        ts_str = format_timestamp(timestamp_ms)

        if entry_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="震荡低点反弹",
                summary=f"{ctx.symbol} oscillation 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "RSI/Stoch超卖 + 5m金叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        if short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="震荡高点回落",
                summary=f"{ctx.symbol} oscillation 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "RSI/Stoch超买 + 5m死叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        return None
