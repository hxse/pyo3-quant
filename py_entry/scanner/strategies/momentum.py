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
class MomentumStrategy(StrategyProtocol):
    """
    动量爆发策略 (Rust 引擎版)

    逻辑：
    - 结合 1w, 1d, 1h, 5m 四个周期
    - 1w: 趋势 (MACD增强 + K线连涨)
    - 1d: 确认 (MACD红 + 也就是均线上)
    - 1h: 加油 (零上红柱)
    - 5m: 起爆 (零上金叉)
    """

    name: Final[str] = "momentum"

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 0. 检查数据
        required_tfs = [TF_5M, TF_1H, TF_1D, TF_1W]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        # 我们需要在所有相关周期上计算指标
        indicators = {
            DK_1W: {
                "macd_w": {  # 周线 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
            DK_1D: {
                "macd_d": {  # 日线 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_d": {"period": Param.create(20)},  # 日线 EMA20
            },
            DK_1H: {
                "macd_h": {  # 小时 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
            DK_5M: {
                "macd_m": {  # 5分钟 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
        }

        # 2. 信号逻辑 (Rust 表达式列表)

        # --- 做多逻辑 ---
        entry_comparisons = [
            # 1. 周线: MACD柱强 (当前>0 且 当前>=上一个) + Price (当前>开盘 且 当前>上一个收盘)
            f"macd_w_hist,{DK_1W},0 > 0",
            f"macd_w_hist,{DK_1W},1 >= macd_w_hist,{DK_1W},1",  # 这里可能是原逻辑有误，或者是写错了。macd_w_hist,ohlcv_1w,0 >= macd_w_hist,ohlcv_1w,1
            f"close,{DK_1W},0 > open,{DK_1W},0",
            f"close,{DK_1W},0 > close,{DK_1W},1",
            # 2. 日线: MACD红 + Close > EMA
            f"macd_d_hist,{DK_1D},0 > 0",
            f"close,{DK_1D},0 > ema_d,{DK_1D},0",
            # 3. 1小时: 零上红柱 (Diff>0, Hist>0)
            # 猜测: DIF 是 macd
            f"macd_h_macd,{DK_1H},0 > 0",
            f"macd_h_hist,{DK_1H},0 > 0",
            # 4. 5分钟: 零上金叉 (Diff>0, Hist由负/零转正)
            f"macd_m_macd,{DK_5M},0 > 0",
            f"macd_m_hist,{DK_5M},0 x> 0",
        ]
        # 修正上方的错误 (macd_w_hist,DK_1W,0 >= macd_w_hist,DK_1W,1)
        entry_comparisons[1] = f"macd_w_hist,{DK_1W},0 >= macd_w_hist,{DK_1W},1"

        # --- 做空逻辑 ---
        exit_comparisons = [
            # 1. 周线: MACD走弱 (当前<0 且 当前<=上一个(更负)) + Price (当前<开盘 且 当前<上一个收盘)
            f"macd_w_hist,{DK_1W},0 < 0",
            f"macd_w_hist,{DK_1W},0 <= macd_w_hist,{DK_1W},1",
            f"close,{DK_1W},0 < open,{DK_1W},0",
            f"close,{DK_1W},0 < close,{DK_1W},1",
            # 2. 日线: MACD绿 + Close < EMA
            f"macd_d_hist,{DK_1D},0 <= 0",
            f"close,{DK_1D},0 < ema_d,{DK_1D},0",
            # 3. 1小时: 零下绿柱 (Diff<0, Hist<0)
            f"macd_h_macd,{DK_1H},0 < 0",
            f"macd_h_hist,{DK_1H},0 < 0",
            # 4. 5分钟: 零下死叉 (Diff<0, Hist由正转负)
            f"macd_m_macd,{DK_5M},0 < 0",
            f"macd_m_hist,{DK_5M},0 x< 0",
        ]

        # 3. 构造请求
        template = SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=entry_comparisons),
            entry_short=SignalGroup(logic=LogicOp.AND, comparisons=exit_comparisons),
        )

        # 4. 运行回测 (使用 helper)
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
                trigger="5m 动量起爆 (多)",
                summary=f"{ctx.symbol} momentum 做多",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日/1H/5m 四周期动量共振",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        elif exit_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="5m 动量起爆 (空)",
                summary=f"{ctx.symbol} momentum 做空",
                detail_lines=[
                    f"时间: {ts_str}",
                    f"价格: {price}",
                    "条件: 周/日/1H/5m 四周期动量共振 (空)",
                ],
                metadata={"price": price, "time": timestamp_ms},
            )
        return None
