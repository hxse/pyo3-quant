"""核心回测模块回归护栏测试。"""

import polars as pl
import pyo3_quant
import pytest

from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
)
from py_entry.Test.shared import make_data_generation_params, make_engine_settings


def _build_minimal_runner(
    num_bars: int,
    backtest_params: BacktestParams | None = None,
    *,
    include_indicators: bool = True,
) -> Backtest:
    """构建最小可运行回测实例。"""
    timeframe = "15m"
    base_key = f"ohlcv_{timeframe}"

    # 这里固定 seed，确保回归测试结果稳定可复现。
    data_source = make_data_generation_params(
        timeframes=[timeframe],
        num_bars=num_bars,
        fixed_seed=7,
        base_data_key=base_key,
        allow_gaps=True,
    )

    indicators = (
        {
            base_key: {
                "sma_fast": {"period": Param(2)},
                "sma_slow": {"period": Param(3)},
            }
        }
        if include_indicators
        else {}
    )

    # 使用交叉信号模板，确保能完整走通 signal -> backtest 管线。
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {base_key}, 0 x> sma_slow, {base_key}, 0",
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {base_key}, 0 x< sma_slow, {base_key}, 0",
            ],
        ),
        exit_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {base_key}, 0 x< sma_slow, {base_key}, 0",
            ],
        ),
        exit_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {base_key}, 0 x> sma_slow, {base_key}, 0",
            ],
        ),
    )

    # 这里故意直接构造 Backtest：该文件是最小回归护栏测试，
    # 需要显式暴露底层组装路径，避免 helper 层掩盖问题。
    return Backtest(
        data_source=data_source,
        indicators=indicators,
        backtest=backtest_params,
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance,
            return_only_final=False,
        ),
    )


class TestAtrColumnRegression:
    """ATR 输出列回归测试。"""

    def test_atr_column_exists_when_any_atr_risk_enabled(self):
        """启用任一 ATR 风控参数时，回测结果必须输出 atr 列。"""
        params = BacktestParams(
            initial_capital=10_000.0,
            fee_fixed=0.0,
            fee_pct=0.0,
            sl_atr=Param(2.0),
            atr_period=Param(14.0),
            sl_exit_in_bar=False,
            tp_exit_in_bar=False,
            sl_trigger_mode=False,
            tp_trigger_mode=False,
            tsl_trigger_mode=False,
        )
        runner = _build_minimal_runner(num_bars=120, backtest_params=params)
        result = runner.run()
        df = result.summary.backtest_result
        assert df is not None, "backtest_result 不应为空"

        assert "atr" in df.columns, "启用 ATR 风控参数后，输出缺少 atr 列"
        assert df["atr"].dtype == pl.Float64, (
            f"atr 列类型应为 Float64，实际为 {df['atr'].dtype}"
        )

        # 预热后至少应有一部分有效 ATR 值。
        valid_count = len(df.filter(pl.col("atr").is_not_nan()))
        assert valid_count > 0, "atr 列全部为 NaN，疑似未正确写入"


class TestShortDatasetRegression:
    """短样本边界回归测试。"""

    @pytest.mark.parametrize("num_bars", [1, 2])
    def test_balance_and_equity_initialized_for_short_dataset(self, num_bars: int):
        """len<=2 时不应返回全零资金列。"""
        initial_capital = 12_345.0
        params = BacktestParams(
            initial_capital=initial_capital,
            fee_fixed=0.0,
            fee_pct=0.0,
        )
        runner = _build_minimal_runner(num_bars=num_bars, backtest_params=params)
        result = runner.run()
        df = result.summary.backtest_result
        assert df is not None, "backtest_result 不应为空"

        assert df.height == num_bars, f"回测结果行数应为 {num_bars}"
        assert (df["balance"] == initial_capital).all(), (
            "短样本下 balance 应初始化为 initial_capital"
        )
        assert (df["equity"] == initial_capital).all(), (
            "短样本下 equity 应初始化为 initial_capital"
        )
        assert (df["current_drawdown"] == 0.0).all(), "短样本下 current_drawdown 应为 0"


class TestBacktestParamDefaultsAndValidation:
    """参数默认值与组合校验回归测试。"""

    def test_default_execution_flags_are_false(self):
        """BacktestParams 默认执行开关应为 False。"""
        params = BacktestParams()
        assert params.sl_exit_in_bar is False
        assert params.tp_exit_in_bar is False
        assert params.sl_trigger_mode is False
        assert params.tp_trigger_mode is False
        assert params.tsl_trigger_mode is False

    @pytest.mark.parametrize(
        "params, expected_msg",
        [
            (
                BacktestParams(
                    sl_exit_in_bar=True,
                    sl_trigger_mode=False,
                    tp_exit_in_bar=False,
                    tp_trigger_mode=False,
                ),
                "sl_exit_in_bar",
            ),
            (
                BacktestParams(
                    sl_exit_in_bar=False,
                    sl_trigger_mode=False,
                    tp_exit_in_bar=True,
                    tp_trigger_mode=False,
                ),
                "tp_exit_in_bar",
            ),
        ],
    )
    def test_invalid_exit_in_bar_trigger_mode_combination_raises(
        self,
        params: BacktestParams,
        expected_msg: str,
    ):
        """exit_in_bar 与 close-trigger 组合应在运行时被拒绝。"""
        runner = _build_minimal_runner(num_bars=40, backtest_params=params)
        with pytest.raises(
            pyo3_quant.errors.PyInvalidParameterError, match=expected_msg
        ):
            runner.run()


class TestHasLeadingNanPassthrough:
    """has_leading_nan 透传回归测试。"""

    def test_backtest_output_passthroughs_has_leading_nan_when_present(self):
        """signals 包含 has_leading_nan 时，backtest 输出应透传且值一致。"""
        runner = _build_minimal_runner(num_bars=80, include_indicators=True)
        summary = runner.run().summary

        signals_df = summary.signals
        backtest_df = summary.backtest_result
        assert signals_df is not None, "signals 不应为空"
        assert backtest_df is not None, "backtest_result 不应为空"

        assert "has_leading_nan" in signals_df.columns, (
            "signals 结果应包含 has_leading_nan"
        )
        assert "has_leading_nan" in backtest_df.columns, (
            "backtest 结果应透传 has_leading_nan"
        )
        assert (
            signals_df["has_leading_nan"] == backtest_df["has_leading_nan"]
        ).all(), "has_leading_nan 透传值不一致"

    def test_backtest_output_omits_has_leading_nan_when_input_missing(self):
        """signals 不包含 has_leading_nan 时，backtest 输出不应凭空生成该列。"""
        runner = _build_minimal_runner(num_bars=80, include_indicators=True)
        summary = runner.run().summary

        signals_df = summary.signals
        assert signals_df is not None, "signals 不应为空"
        signals_without_nan_col = signals_df.drop("has_leading_nan")

        df = pyo3_quant.backtest_engine.backtester.run_backtest(
            runner.data_dict,
            signals_without_nan_col,
            runner.params.backtest,
        )
        assert "has_leading_nan" not in df.columns, (
            "输入 signals 缺少 has_leading_nan 时，backtest 输出不应包含该列"
        )
