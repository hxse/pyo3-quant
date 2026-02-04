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
class ReversalStrategy(StrategyProtocol):
    """
    极值背驰策略 (Reversal - Rust 引擎版)

    逻辑 (完全匹配 manual_trading.md 1.3):
    - 周线: 强势多头/空头背景 (CCI > 80 / < -80)
    - 日线: 极值背离 (CCI-Divergence, recency=5)
    - 1小时: 动能反转 (MACD 红转绿 / 绿转红)
    - 5分钟: 共振杀跌/反弹 (MACD 触发 + 破小均线 + 破中均线 + 受阻大均线)
    """

    name: Final[str] = "reversal"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = [TF_5M, TF_1H, TF_1D, TF_1W]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            DK_1W: {
                # 周线: 仅需 CCI 判断背景 + EMA 趋势过滤
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            DK_1D: {
                # 日线: 核心是 CCI 背离 (API重构: 一次性返回 top/bottom, 废弃 mode)
                "cci-divergence_0": {
                    "period": Param.create(14),
                    "window": Param.create(20),
                    "gap": Param.create(3),
                    "recency": Param.create(5),
                },
                "ema_d": {"period": Param.create(20)},
            },
            DK_1H: {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_h": {"period": Param.create(20)},
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

        # --- 做多逻辑 (底背离反转: 抓空头回调/见底) ---
        long_filter = [
            # 1. [周线] 极度弱势背景
            f"cci_w,{DK_1W},0 < -80",
            f"close,{DK_1W},0 < ema_w,{DK_1W},0",
            # 2. [日线] 弱势中的底背离
            f"close,{DK_1D},0 < ema_d,{DK_1D},0",
            f"cci-divergence_0_bottom,{DK_1D},0 > 0.5",
            # 3. [1小时] 动能转折 (红柱)
            f"macd_h_hist,{DK_1H},0 > 0",
            # 4. [空间约束] 黄金窗口: 1h < Close < 1d
            f"close,{DK_5M},0 > ema_h,{DK_1H},0",
            f"close,{DK_5M},0 < ema_d,{DK_1D},0",
        ]

        # 5m 做多触发 (OR)
        long_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_m_hist,{DK_5M},0 > 0",
                        f"close,{DK_5M},0 x> ema_m,{DK_5M},0",
                    ],
                ),
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"close,{DK_5M},0 > ema_m,{DK_5M},0",
                        f"macd_m_hist,{DK_5M},0 x> 0",
                    ],
                ),
            ],
        )

        # --- 做空逻辑 (顶背离反转: 抓多头回调/见顶) ---
        short_filter = [
            # 1. [周线] 极度强势背景
            f"cci_w,{DK_1W},0 > 80",
            f"close,{DK_1W},0 > ema_w,{DK_1W},0",
            # 2. [日线] 强势中的顶背离
            f"close,{DK_1D},0 > ema_d,{DK_1D},0",
            f"cci-divergence_0_top,{DK_1D},0 > 0.5",
            # 3. [1小时] 动能转折 (绿柱)
            f"macd_h_hist,{DK_1H},0 < 0",
            # 4. [空间约束] 夹逼区间: 1d < Close < 1h
            f"close,{DK_5M},0 < ema_h,{DK_1H},0",
            f"close,{DK_5M},0 > ema_d,{DK_1D},0",
        ]

        # 5m 做空触发 (OR)
        short_trigger_group = SignalGroup(
            logic=LogicOp.OR,
            sub_groups=[
                SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_m_hist,{DK_5M},0 < 0",
                        f"close,{DK_5M},0 x< ema_m,{DK_5M},0",
                    ],
                ),
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
                trigger="Reversal 底背离",
                summary=f"{ctx.symbol} reversal 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 1d底背离 + 1H MACD金叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        if short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Reversal 顶背离",
                summary=f"{ctx.symbol} reversal 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 1d顶背离 + 1H MACD死叉",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        return None
