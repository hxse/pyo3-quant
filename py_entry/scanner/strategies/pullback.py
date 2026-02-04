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
        required_tfs = [TF_5M, TF_1H, TF_1D, TF_1W]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            DK_1W: {
                "macd_w": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_w": {"period": Param.create(20)},
            },
            DK_1D: {
                "macd_d": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
            },
            DK_1H: {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
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
        # 5m 触发公式: (MACD同向 AND close x> EMA) OR (close > EMA AND MACD x> 0)

        # --- 做多逻辑 (周线强多 -> 日线弱回调 -> 1H回多 -> 5m启动) ---
        entry_comparisons = [
            # 1. [周线] 强多头
            f"macd_w_hist,{DK_1W},0 > 0",  # 红柱
            f"macd_w_macd,{DK_1W},0 > 0",  # 快线零上 (确保是多头趋势而非空头反弹)
            f"close,{DK_1W},0 > ema_w,{DK_1W},0",  # 价格在均线上
            # 2. [日线] 次级回调 (红柱变蓝柱 / 或者是蓝柱)
            # 关键: 是回调而非反转 -> 快线必须还在零上!
            f"macd_d_hist,{DK_1D},0 < 0",  # 蓝柱 (回调中)
            f"macd_d_macd,{DK_1D},0 > 0",  # 但快线 > 0 (结构未坏)
            # 3. [1小时] 回调结束 (重回红柱)
            f"macd_h_hist,{DK_1H},0 > 0",
            # 4. [5分钟] 刚刚触发 (OR逻辑)
            # 这里通过 SignalTemplate 将 Trigger 部分作为 sub_group 嵌入
            # 由于外层已经是 AND，我们在外层只写 1~3 的 AND
            # 第 4 部分由 long_trigger_group 处理
        ]

        # --- 做空逻辑 (周线强空 -> 日线弱反弹 -> 1H回空 -> 5m启动) ---
        exit_comparisons = [
            # 1. [周线] 强空头
            f"macd_w_hist,{DK_1W},0 < 0",  # 蓝柱
            f"macd_w_macd,{DK_1W},0 < 0",  # 快线零下
            f"close,{DK_1W},0 < ema_w,{DK_1W},0",
            # 2. [日线] 次级反弹
            f"macd_d_hist,{DK_1D},0 > 0",  # 红柱 (反弹中)
            f"macd_d_macd,{DK_1D},0 < 0",  # 但快线 < 0 (结构未坏)
            # 3. [1小时] 反弹结束
            f"macd_h_hist,{DK_1H},0 < 0",
        ]

        # 5m 做多触发 (OR)
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

        # 5m 做空触发 (OR)
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
                comparisons=entry_comparisons,
                sub_groups=[long_trigger_group],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                comparisons=exit_comparisons,
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
                trigger="Pullback 趋势回调",
                summary=f"{ctx.symbol} pullback 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日CCI强 + 5m MACD回踩(Diff>0 且 Hist>0)",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        elif short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Pullback 趋势反弹",
                summary=f"{ctx.symbol} pullback 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日CCI弱 + 5m MACD反弹(Diff<0 且 Hist<0)",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
