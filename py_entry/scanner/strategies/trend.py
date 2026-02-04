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
class TrendStrategy(StrategyProtocol):
    """
    强趋势共振策略 (Trend - Rust 引擎版)

    逻辑 (完全匹配 manual_trading.md 1.2):
    - 周线: CCI > 80 AND Close > EMA
    - 日线: CCI > 30 AND Close > EMA
    - 1小时: MACD红柱 AND Close > EMA
    - 5分钟: (MACD红柱 AND close x> EMA) OR (close > EMA AND MACD红柱上穿0)
    """

    name: Final[str] = "trend"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = [TF_5M, TF_1H, TF_1D, TF_1W]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            DK_1W: {
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            DK_1D: {
                "cci_d": {"period": Param.create(14)},
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

        # 2. 信号逻辑
        # 文档结构: 大周期过滤 (AND) + 5m触发 (OR: 穿越 vs 开盘)

        # --- 共通的大周期过滤条件 ---
        long_filter = [
            # 周线
            f"cci_w,{DK_1W},0 > 80",
            f"close,{DK_1W},0 > ema_w,{DK_1W},0",
            # 日线
            f"cci_d,{DK_1D},0 > 30",
            f"close,{DK_1D},0 > ema_d,{DK_1D},0",
            # 1小时
            f"macd_h_hist,{DK_1H},0 > 0",
            f"close,{DK_1H},0 > ema_h,{DK_1H},0",
        ]

        short_filter = [
            # 周线 (做空对称)
            f"cci_w,{DK_1W},0 < -80",
            f"close,{DK_1W},0 < ema_w,{DK_1W},0",
            # 日线
            f"cci_d,{DK_1D},0 < -30",
            f"close,{DK_1D},0 < ema_d,{DK_1D},0",
            # 1小时
            f"macd_h_hist,{DK_1H},0 < 0",
            f"close,{DK_1H},0 < ema_h,{DK_1H},0",
        ]

        # --- 5m 触发条件 (OR) ---
        # 做多触发: (MACD红柱 AND 上穿EMA) OR (站上EMA AND MACD金叉/转红)
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

        # 做空触发: 对称逻辑
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
        entry_signal = signal_dict.get("entry_long", 0.0)
        exit_signal = signal_dict.get("entry_short", 0.0)

        # 格式化时间
        ts_str = format_timestamp(timestamp_ms)

        if entry_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="Trend 突破进场",
                summary=f"{ctx.symbol} trend 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日CCI强 + 1H红柱 + 5m红柱/突破EMA共振",
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
                trigger="Trend 向下突破",
                summary=f"{ctx.symbol} trend 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日CCI弱 + 1H绿柱 + 5m绿柱/跌破EMA共振",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )

        return None
