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
        required_tfs = ["5m", "1h", "1d", "1w"]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        indicators = {
            "ohlcv_1w": {
                # 周线: 仅需 CCI 判断背景 + EMA 趋势过滤
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            "ohlcv_1d": {
                # 日线: 核心是 CCI 背离 (API重构: 一次性返回 top/bottom, 废弃 mode)
                "cci-divergence_0": {
                    "period": Param.create(14),
                    "window": Param.create(20),
                    "gap": Param.create(3),
                    "recency": Param.create(5),
                },
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
        entry_comparisons = [
            # 1. [周线] 极度弱势背景
            "cci_w,ohlcv_1w,0 < -80",
            "close,ohlcv_1w,0 < ema_w,ohlcv_1w,0",
            # 2. [日线] 弱势中的底背离
            "close,ohlcv_1d,0 < ema_d,ohlcv_1d,0",
            "cci-divergence_0_bottom,ohlcv_1d,0 > 0.5",
            # 3. [1小时] 动能转折
            "macd_h_hist,ohlcv_1h,0 > 0",
            # 4. [5分钟] 入场触发
            "macd_m_hist,ohlcv_5m,0 > 0",
            "macd_m_hist,ohlcv_5m,0 > macd_m_hist,ohlcv_5m,1",
            "close,ohlcv_5m,0 > ema_m,ohlcv_5m,0",  # 站上5m EMA
            "close,ohlcv_5m,0 > ema_h,ohlcv_1h,0",  # 站上1h EMA
            "close,ohlcv_5m,0 < ema_d,ohlcv_1d,0",  # 仍受压于日线 EMA (吃鱼身)
        ]

        # --- 做空逻辑 (顶背离反转: 抓多头回调/见顶) ---
        exit_comparisons = [
            # 1. [周线] 极度强势背景
            "cci_w,ohlcv_1w,0 > 80",
            "close,ohlcv_1w,0 > ema_w,ohlcv_1w,0",
            # 2. [日线] 强势中的顶背离
            "close,ohlcv_1d,0 > ema_d,ohlcv_1d,0",
            "cci-divergence_0_top,ohlcv_1d,0 > 0.5",
            # 3. [1小时] 动能转折
            "macd_h_hist,ohlcv_1h,0 < 0",
            # 4. [5分钟] 入场触发
            "macd_m_hist,ohlcv_5m,0 < 0",
            "macd_m_hist,ohlcv_5m,0 < macd_m_hist,ohlcv_5m,1",
            "close,ohlcv_5m,0 < ema_m,ohlcv_5m,0",  # 跌破5m EMA
            "close,ohlcv_5m,0 < ema_h,ohlcv_1h,0",  # 跌破1h EMA
            "close,ohlcv_5m,0 > ema_d,ohlcv_1d,0",  # 仍支撑于日线 EMA (吃鱼身)
        ]

        template = SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=entry_comparisons),
            entry_short=SignalGroup(logic=LogicOp.AND, comparisons=exit_comparisons),
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

        if entry_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="Reversal 底背离反转",
                summary=f"{ctx.symbol} 触发极值底背离",
                detail_lines=["价格: {price}", "背离类型: CCI底背离(日)"],
                metadata={"price": price},
            )

        if short_sig > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="Reversal 顶背离反转",
                summary=f"{ctx.symbol} 触发极值顶背离",
                detail_lines=["价格: {price}", "背离类型: CCI顶背离(日)"],
                metadata={"price": price},
            )

        return None
