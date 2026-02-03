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
        required_tfs = ["5m", "1h", "1d", "1w"]
        ctx.validate_klines_existence(required_tfs)

        # 1. 准备参数
        # 我们需要在所有相关周期上计算指标
        indicators = {
            "ohlcv_1w": {
                "macd_w": {  # 周线 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
            "ohlcv_1d": {
                "macd_d": {  # 日线 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_d": {"period": Param.create(20)},  # 日线 EMA20
            },
            "ohlcv_1h": {
                "macd_h": {  # 小时 MACD
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                }
            },
            "ohlcv_5m": {
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
            "macd_w_hist,ohlcv_1w,0 > 0",
            "macd_w_hist,ohlcv_1w,0 >= macd_w_hist,ohlcv_1w,1",
            "close,ohlcv_1w,0 > open,ohlcv_1w,0",
            "close,ohlcv_1w,0 > close,ohlcv_1w,1",
            # 2. 日线: MACD红 + Close > EMA
            "macd_d_hist,ohlcv_1d,0 > 0",
            "close,ohlcv_1d,0 > ema_d,ohlcv_1d,0",
            # 3. 1小时: 零上红柱 (Diff>0, Hist>0)
            # 猜测: DIF 是 macd
            "macd_h_macd,ohlcv_1h,0 > 0",
            "macd_h_hist,ohlcv_1h,0 > 0",
            # 4. 5分钟: 零上金叉 (Diff>0, Hist由负/零转正)
            "macd_m_macd,ohlcv_5m,0 > 0",
            "macd_m_hist,ohlcv_5m,0 x> 0",
        ]

        # --- 做空逻辑 ---
        exit_comparisons = [
            # 1. 周线: MACD走弱 (当前<0 且 当前<=上一个(更负)) + Price (当前<开盘 且 当前<上一个收盘)
            "macd_w_hist,ohlcv_1w,0 < 0",
            "macd_w_hist,ohlcv_1w,0 <= macd_w_hist,ohlcv_1w,1",
            "close,ohlcv_1w,0 < open,ohlcv_1w,0",
            "close,ohlcv_1w,0 < close,ohlcv_1w,1",
            # 2. 日线: MACD绿 + Close < EMA
            "macd_d_hist,ohlcv_1d,0 <= 0",  # 注意：旧版逻辑是 <0 还是 <=0? 旧版是 if hist <= 0 return None (即必须>0是做多). 做空是 if hist >= 0 return None (即必须 <0)
            "close,ohlcv_1d,0 < ema_d,ohlcv_1d,0",
            # 3. 1小时: 零下绿柱 (Diff<0, Hist<0)
            "macd_h_macd,ohlcv_1h,0 < 0",
            "macd_h_hist,ohlcv_1h,0 < 0",
            # 4. 5分钟: 零下死叉 (Diff<0, Hist由正转负)
            "macd_m_macd,ohlcv_5m,0 < 0",
            "macd_m_hist,ohlcv_5m,0 x< 0",
        ]

        # 3. 构造请求
        template = SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=entry_comparisons),
            entry_short=SignalGroup(logic=LogicOp.AND, comparisons=exit_comparisons),
        )

        # 4. 转换数据
        # 即使只用 5m 作为 base，Rust Engine 会根据 mapping 自动找到其他周期对应的数据
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
        entry_signal = last_row["entry_long"][0]
        exit_signal = last_row["entry_short"][0]

        # 辅助: 获取当前价格
        price = data.source["ohlcv_5m"].select(pl.col("close")).tail(1).item()
        metadata = {"price": price}

        if entry_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="long",
                trigger="5m 动量起爆 (多)",
                summary=f"{ctx.symbol} 触发动量起爆做多信号",
                detail_lines=[f"价格: {price}", "多周期动量共振 (1w/1d/1h/5m)"],
                metadata=metadata,
            )

        if exit_signal > 0.5:
            return StrategySignal(
                strategy_name=self.name,
                symbol=ctx.symbol,
                direction="short",
                trigger="5m 动量跳水 (空)",
                summary=f"{ctx.symbol} 触发动量跳水做空信号",
                detail_lines=[f"价格: {price}", "多周期动量共振空头 (1w/1d/1h/5m)"],
                metadata=metadata,
            )

        return None
