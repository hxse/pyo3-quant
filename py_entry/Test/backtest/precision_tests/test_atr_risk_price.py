"""
精细化测试: ATR 风控价格验证

验证 sl_atr_price, tp_atr_price, tsl_atr_price 的计算正确性:

公式 (来自 risk_check.rs):
    - sl_atr_price_long = entry_price - atr * sl_atr_multiplier
    - sl_atr_price_short = entry_price + atr * sl_atr_multiplier
    - tp_atr_price_long = entry_price + atr * tp_atr_multiplier
    - tp_atr_price_short = entry_price - atr * tp_atr_multiplier

    其中:
    - atr 使用 pandas-ta.atr(talib=True) 计算
    - 价格只在 first_entry_side 时设置，后续 bar 保持不变
"""

import pandas as pd
import pandas_ta as ta
import polars as pl
import pytest


def _calculate_reference_atr(
    close_series: pl.Series, high_series: pl.Series, low_series: pl.Series, period: int
) -> pl.Series:
    """使用 pandas-ta 计算参考 ATR 值"""
    # 转换为 pandas
    df = pd.DataFrame(
        {
            "high": high_series.to_numpy(),
            "low": low_series.to_numpy(),
            "close": close_series.to_numpy(),
        }
    )

    # 使用 talib 模式计算 ATR
    atr = ta.atr(df["high"], df["low"], df["close"], length=period, talib=True)

    return pl.Series("atr", atr.to_numpy())


class TestAtrRiskPriceCalculation:
    """测试 ATR 风控价格的计算正确性"""

    def test_sl_atr_price_long_formula(self, backtest_with_config):
        """验证多头 ATR 止损价格: sl_atr_price_long = signal_close - signal_atr * sl_atr"""
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        # 检查是否启用了 sl_atr
        if backtest_params.sl_atr is None or backtest_params.sl_atr.value == 0:
            pytest.skip("策略未启用 sl_atr")

        sl_atr_multiplier = backtest_params.sl_atr.value
        atr_period = (
            backtest_params.atr_period.value if backtest_params.atr_period else 14
        )

        df = results[0].backtest_result

        # 检查是否有 sl_atr_price_long 列
        if "sl_atr_price_long" not in df.columns:
            pytest.skip("回测结果无 sl_atr_price_long 列")

        # 获取基础数据计算参考 ATR
        base_key = data_dict.BaseDataKey
        base_data = data_dict.source[base_key]
        ref_atr = _calculate_reference_atr(
            base_data["close"], base_data["high"], base_data["low"], atr_period
        )

        # 添加参考 Signal Close 和 Signal ATR 到 df
        # 注意: Pyo3 Signal是基于 prev_bar (i-1)
        base_close = base_data["close"]
        df = df.with_columns(
            [
                base_close.shift(1).alias("signal_close"),
                ref_atr.shift(1).alias("signal_atr"),
            ]
        )

        # 使用 first_entry_side 列直接筛选多头首次进场
        df = df.with_columns((pl.col("first_entry_side") == 1).alias("is_first_entry"))

        first_entries = df.filter(
            pl.col("is_first_entry")
            & pl.col("sl_atr_price_long").is_not_nan()
            & pl.col("signal_atr").is_not_nan()
        )

        if len(first_entries) == 0:
            pytest.skip("无多头首次进场记录")

        # 验证公式: sl_atr_price = signal_close - signal_atr * multiplier
        first_entries = first_entries.with_columns(
            (pl.col("signal_close") - pl.col("signal_atr") * sl_atr_multiplier).alias(
                "expected_sl_price"
            )
        ).with_columns(
            (pl.col("sl_atr_price_long") - pl.col("expected_sl_price"))
            .abs()
            .alias("price_diff")
        )

        tolerance = 1e-6
        errors = first_entries.filter(pl.col("price_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ sl_atr_price_long 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "signal_close",
                        "signal_atr",
                        "sl_atr_price_long",
                        "expected_sl_price",
                        "price_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 sl_atr_price_long 计算错误")

        print(f"✅ {len(first_entries)} 个多头进场点 sl_atr_price_long 计算正确")

    def test_sl_atr_price_short_formula(self, backtest_with_config):
        """验证空头 ATR 止损价格: sl_atr_price_short = signal_close + signal_atr * sl_atr"""
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        if backtest_params.sl_atr is None or backtest_params.sl_atr.value == 0:
            pytest.skip("策略未启用 sl_atr")

        sl_atr_multiplier = backtest_params.sl_atr.value
        atr_period = (
            backtest_params.atr_period.value if backtest_params.atr_period else 14
        )

        df = results[0].backtest_result

        if "sl_atr_price_short" not in df.columns:
            pytest.skip("回测结果无 sl_atr_price_short 列")

        base_key = data_dict.BaseDataKey
        base_data = data_dict.source[base_key]
        ref_atr = _calculate_reference_atr(
            base_data["close"], base_data["high"], base_data["low"], atr_period
        )

        # Signal Basis
        base_close = base_data["close"]
        df = df.with_columns(
            [
                base_close.shift(1).alias("signal_close"),
                ref_atr.shift(1).alias("signal_atr"),
            ]
        )

        # 使用 first_entry_side 列直接筛选空头首次进场
        df = df.with_columns((pl.col("first_entry_side") == -1).alias("is_first_entry"))

        first_entries = df.filter(
            pl.col("is_first_entry")
            & pl.col("sl_atr_price_short").is_not_nan()
            & pl.col("signal_atr").is_not_nan()
        )

        if len(first_entries) == 0:
            pytest.skip("无空头首次进场记录")

        # 验证公式: sl_atr_price = signal_close + signal_atr * multiplier
        first_entries = first_entries.with_columns(
            (pl.col("signal_close") + pl.col("signal_atr") * sl_atr_multiplier).alias(
                "expected_sl_price"
            )
        ).with_columns(
            (pl.col("sl_atr_price_short") - pl.col("expected_sl_price"))
            .abs()
            .alias("price_diff")
        )

        tolerance = 1e-6
        errors = first_entries.filter(pl.col("price_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ sl_atr_price_short 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "signal_close",
                        "signal_atr",
                        "sl_atr_price_short",
                        "expected_sl_price",
                        "price_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 sl_atr_price_short 计算错误")

        print(f"✅ {len(first_entries)} 个空头进场点 sl_atr_price_short 计算正确")

    def test_tp_atr_price_long_formula(self, backtest_with_config):
        """验证多头 ATR 止盈价格: tp_atr_price_long = signal_close + signal_atr * tp_atr"""
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        if backtest_params.tp_atr is None or backtest_params.tp_atr.value == 0:
            pytest.skip("策略未启用 tp_atr")

        tp_atr_multiplier = backtest_params.tp_atr.value
        atr_period = (
            backtest_params.atr_period.value if backtest_params.atr_period else 14
        )

        df = results[0].backtest_result

        if "tp_atr_price_long" not in df.columns:
            pytest.skip("回测结果无 tp_atr_price_long 列")

        base_key = data_dict.BaseDataKey
        base_data = data_dict.source[base_key]
        ref_atr = _calculate_reference_atr(
            base_data["close"], base_data["high"], base_data["low"], atr_period
        )

        # Signal Basis
        base_close = base_data["close"]
        df = df.with_columns(
            [
                base_close.shift(1).alias("signal_close"),
                ref_atr.shift(1).alias("signal_atr"),
            ]
        )

        # 使用 first_entry_side 列直接筛选多头首次进场
        df = df.with_columns((pl.col("first_entry_side") == 1).alias("is_first_entry"))

        first_entries = df.filter(
            pl.col("is_first_entry")
            & pl.col("tp_atr_price_long").is_not_nan()
            & pl.col("signal_atr").is_not_nan()
        )

        if len(first_entries) == 0:
            pytest.skip("无多头首次进场记录")

        # 验证公式: tp_atr_price = signal_close + signal_atr * multiplier
        first_entries = first_entries.with_columns(
            (pl.col("signal_close") + pl.col("signal_atr") * tp_atr_multiplier).alias(
                "expected_tp_price"
            )
        ).with_columns(
            (pl.col("tp_atr_price_long") - pl.col("expected_tp_price"))
            .abs()
            .alias("price_diff")
        )

        tolerance = 1e-6
        errors = first_entries.filter(pl.col("price_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ tp_atr_price_long 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "signal_close",
                        "signal_atr",
                        "tp_atr_price_long",
                        "expected_tp_price",
                        "price_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 tp_atr_price_long 计算错误")

        print(f"✅ {len(first_entries)} 个多头进场点 tp_atr_price_long 计算正确")

    def test_tp_atr_price_short_formula(self, backtest_with_config):
        """验证空头 ATR 止盈价格: tp_atr_price_short = signal_close - signal_atr * tp_atr"""
        results, strategy, data_dict = backtest_with_config
        backtest_params = strategy.backtest_params

        if backtest_params.tp_atr is None or backtest_params.tp_atr.value == 0:
            pytest.skip("策略未启用 tp_atr")

        tp_atr_multiplier = backtest_params.tp_atr.value
        atr_period = (
            backtest_params.atr_period.value if backtest_params.atr_period else 14
        )

        df = results[0].backtest_result

        if "tp_atr_price_short" not in df.columns:
            pytest.skip("回测结果无 tp_atr_price_short 列")

        base_key = data_dict.BaseDataKey
        base_data = data_dict.source[base_key]
        ref_atr = _calculate_reference_atr(
            base_data["close"], base_data["high"], base_data["low"], atr_period
        )

        # Signal Basis
        base_close = base_data["close"]
        df = df.with_columns(
            [
                base_close.shift(1).alias("signal_close"),
                ref_atr.shift(1).alias("signal_atr"),
            ]
        )

        # 使用 first_entry_side 列直接筛选空头首次进场
        df = df.with_columns((pl.col("first_entry_side") == -1).alias("is_first_entry"))

        first_entries = df.filter(
            pl.col("is_first_entry")
            & pl.col("tp_atr_price_short").is_not_nan()
            & pl.col("signal_atr").is_not_nan()
        )

        if len(first_entries) == 0:
            pytest.skip("无空头首次进场记录")

        # 验证公式: tp_atr_price = signal_close - signal_atr * multiplier
        first_entries = first_entries.with_columns(
            (pl.col("signal_close") - pl.col("signal_atr") * tp_atr_multiplier).alias(
                "expected_tp_price"
            )
        ).with_columns(
            (pl.col("tp_atr_price_short") - pl.col("expected_tp_price"))
            .abs()
            .alias("price_diff")
        )

        tolerance = 1e-6
        errors = first_entries.filter(pl.col("price_diff") > tolerance)

        if len(errors) > 0:
            print("\n❌ tp_atr_price_short 计算错误 (前5条):")
            print(
                errors.select(
                    [
                        "signal_close",
                        "signal_atr",
                        "tp_atr_price_short",
                        "expected_tp_price",
                        "price_diff",
                    ]
                ).head(5)
            )
            pytest.fail(f"发现 {len(errors)} 处 tp_atr_price_short 计算错误")

        print(f"✅ {len(first_entries)} 个空头进场点 tp_atr_price_short 计算正确")
