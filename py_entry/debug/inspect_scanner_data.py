"""
调试脚本：获取天勤最新数据并打印 4 个周期的价格及指标数值 (EMA, CCI, MACD)
"""

import logging
from py_entry.scanner.config import ScannerConfig
from py_entry.scanner.data_source import TqDataSource
from py_entry.runner import Backtest
from py_entry.data_generator import DirectDataConfig
from py_entry.types import (
    SettingContainer,
    ExecutionStage,
    Param,
    BacktestParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
)
from tqsdk import TqAuth  # type: ignore
import polars as pl

# 禁用冗余日志
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("inspect_scanner")
logger.setLevel(logging.INFO)


def main():
    # 1. 加载配置和数据源
    config = ScannerConfig()
    if not config.tq_username or not config.tq_password:
        print("错误: 未配置天勤账号。请检查 data/config.json")
        return

    auth = TqAuth(config.tq_username, config.tq_password)
    ds = TqDataSource(auth=auth)

    symbol = "KQ.m@SHFE.rb"  # 默认螺纹钢主力
    # symbol = "SHFE.rb2605"  # 指定螺纹钢 2605
    print(f"\n===== 正在获取 {symbol} 最新数据 =====")

    # 2. 定义指标配置
    # 我们为每个周期计算同样的指标，方便对比
    indicators_params = {
        "ema_20": {"period": Param(20)},
        "cci_14": {"period": Param(14)},
        "macd_0": {
            "fast_period": Param(12),
            "slow_period": Param(26),
            "signal_period": Param(9),
        },
    }

    # 3. 遍历四个周期
    for tf in config.timeframes:
        print(f"\n>>> 周期: {tf.name} ({tf.seconds}s)")

        # 获取 K 线 (获取 100 根保证指标计算准确)
        pdf = ds.get_klines(symbol, tf.seconds, 100)
        if pdf is None or pdf.empty:
            print(f"  未能获取 {tf.name} 数据")
            continue

        # 转换为 Polars DataFrame (引擎需要)
        df = pl.from_pandas(pdf)

        # 4. 调用 pyo3-quant 引擎计算指标
        base_key = f"ohlcv_{tf.name}"

        # 传入空的 SignalTemplate 以避免系统加载默认的 (ohlcv_15m) 模板
        empty_template = SignalTemplate(
            entry_long=SignalGroup(logic=LogicOp.AND, comparisons=[])
        )

        bt = Backtest(
            data_source=DirectDataConfig(data={base_key: df}, base_data_key=base_key),
            indicators={base_key: indicators_params},
            signal_template=empty_template,
            engine_settings=SettingContainer(
                execution_stage=ExecutionStage.Signals, return_only_final=False
            ),
            backtest=BacktestParams(
                initial_capital=10000.0, fee_fixed=0.0, fee_pct=0.0
            ),
        )

        try:
            result = bt.run()
            # 访问 result.summary.indicators (Dict[str, pl.DataFrame])
            if (
                result.summary.indicators is None
                or base_key not in result.summary.indicators
            ):
                print("  计算失败: 未能获取指标结果")
                continue

            # 获取计算后的指标 DataFrame
            indicator_df = result.summary.indicators[base_key]

            # 拼接指标和原始 OHLCV 数据，获得 datetime 和 close 列
            full_df = pl.concat([df, indicator_df], how="horizontal")

            # 转换时间为本地可读格式
            if "datetime" in full_df.columns:
                # 天勤返回的是纳秒级 UNIX 时间戳，转换为本地时间字符串
                full_df = full_df.with_columns(
                    [
                        pl.from_epoch("datetime", time_unit="ns")
                        .dt.convert_time_zone("Asia/Shanghai")
                        .dt.strftime("%Y-%m-%d %H:%M:%S")
                        .alias("time")
                    ]
                )

            # 5. 打印最后 3 行
            # 精简列显示，确保不被截断
            core_cols = ["time", "close", "ema_20", "cci_14", "macd_0_hist"]
            actual_cols = [c for c in core_cols if c in full_df.columns]

            # 使用 Config 确保显示所有列
            with pl.Config(tbl_cols=len(actual_cols), tbl_width_chars=200):
                last_3 = full_df.select(actual_cols).tail(3)
                print(last_3)

        except Exception as e:
            print(f"  引擎计算出错: {e}")

    ds.close()
    print("\n===== 检查完毕 =====")


if __name__ == "__main__":
    main()
