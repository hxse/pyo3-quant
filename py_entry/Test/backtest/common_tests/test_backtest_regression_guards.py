"""核心回测模块回归护栏测试。"""

import polars as pl
import pyo3_quant
import pytest

from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    DataPack,
    ExecutionStage,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
    SourceRange,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import make_engine_settings
from py_entry.Test.shared.constants import TEST_START_TIME_MS


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
    data_source = DataGenerationParams(
        timeframes=[timeframe],
        start_time=TEST_START_TIME_MS,
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
        df = result.result.backtest_result
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

    @pytest.mark.parametrize(
        ("num_bars", "should_raise"),
        [
            (1, True),
            (2, False),
        ],
    )
    def test_balance_and_equity_initialized_for_short_dataset(
        self, num_bars: int, should_raise: bool
    ):
        """短样本契约：1 根数据应被数据层拒绝；2 根数据应完成初始化。"""
        initial_capital = 12_345.0
        params = BacktestParams(
            initial_capital=initial_capital,
            fee_fixed=0.0,
            fee_pct=0.0,
        )
        if should_raise:
            with pytest.raises(ValueError, match="至少需要 2 行"):
                _build_minimal_runner(num_bars=num_bars, backtest_params=params)
            return

        runner = _build_minimal_runner(num_bars=num_bars, backtest_params=params)
        result = runner.run()
        df = result.result.backtest_result
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
    """has_leading_nan 输出边界回归测试。"""

    def test_top_level_backtest_output_omits_has_leading_nan_when_present(self):
        """顶层单次回测结果中，backtest 输出不应继续透传 has_leading_nan。"""
        runner = _build_minimal_runner(num_bars=80, include_indicators=True)
        result = runner.run().result

        signals_df = result.signals
        backtest_df = result.backtest_result
        assert signals_df is not None, "signals 不应为空"
        assert backtest_df is not None, "backtest_result 不应为空"

        assert "has_leading_nan" in signals_df.columns, (
            "signals 结果应包含 has_leading_nan"
        )
        assert "has_leading_nan" not in backtest_df.columns, (
            "顶层 backtest 结果不应继续透传 has_leading_nan"
        )

    def test_backtest_output_omits_has_leading_nan_when_input_missing(self):
        """低层 backtester 在输入缺少该列时，不应凭空生成 has_leading_nan。"""
        runner = _build_minimal_runner(num_bars=80, include_indicators=True)
        result = runner.run().result

        signals_df = result.signals
        assert signals_df is not None, "signals 不应为空"
        signals_without_nan_col = signals_df.drop("has_leading_nan")

        df = pyo3_quant.backtest_engine.backtester.run_backtest(
            runner.data_pack,
            signals_without_nan_col,
            runner.params.backtest,
        )
        assert "has_leading_nan" not in df.columns, (
            "输入 signals 缺少 has_leading_nan 时，backtest 输出不应包含该列"
        )

    def test_backtest_output_omits_has_leading_nan_when_input_present(self):
        """低层 backtester 即使收到该列，也不应继续把它透传到 backtest 输出。"""
        runner = _build_minimal_runner(num_bars=80, include_indicators=True)
        result = runner.run().result

        signals_df = result.signals
        assert signals_df is not None, "signals 不应为空"
        assert "has_leading_nan" in signals_df.columns, (
            "signals 结果应包含 has_leading_nan"
        )

        df = pyo3_quant.backtest_engine.backtester.run_backtest(
            runner.data_pack,
            signals_df,
            runner.params.backtest,
        )
        assert "has_leading_nan" not in df.columns, (
            "低层 backtester 不应继续透传 has_leading_nan"
        )


class TestWarmupEntrySuppression:
    """预热禁开仓必须在信号模块内部完成。"""

    def test_signal_module_suppresses_entry_by_base_warmup_range(self):
        """仅由 backtest-exec warmup 产生的预热区，也必须在 signals 中禁开仓。"""
        base_key = "ohlcv_15m"
        runner = Backtest(
            data_source=DataGenerationParams(
                timeframes=["15m"],
                start_time=TEST_START_TIME_MS,
                num_bars=80,
                fixed_seed=11,
                base_data_key=base_key,
                allow_gaps=False,
            ),
            indicators={},
            backtest=BacktestParams(
                initial_capital=10_000.0,
                fee_fixed=0.0,
                fee_pct=0.0,
                sl_atr=Param(2.0),
                atr_period=Param(5.0),
                sl_exit_in_bar=False,
                tp_exit_in_bar=False,
                sl_trigger_mode=False,
                tp_trigger_mode=False,
                tsl_trigger_mode=False,
            ),
            signal_template=SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"close, {base_key}, 0 > -1"],
                ),
                entry_short=None,
                exit_long=None,
                exit_short=None,
            ),
            engine_settings=make_engine_settings(
                execution_stage=ExecutionStage.Signals,
                return_only_final=False,
            ),
        )

        warmup_bars = 5
        source_df = runner.data_pack.source[base_key]
        custom_data_pack = DataPack(
            mapping=runner.data_pack.mapping,
            skip_mask=runner.data_pack.skip_mask,
            source=runner.data_pack.source,
            base_data_key=base_key,
            ranges={
                base_key: SourceRange(
                    warmup_bars=warmup_bars,
                    active_bars=source_df.height - warmup_bars,
                    pack_bars=source_df.height,
                )
            },
        )
        signals = pyo3_quant.backtest_engine.signal_generator.generate_signals(
            custom_data_pack,
            {},
            runner.params.signal,
            runner.template_config.signal,
        )

        assert signals["has_leading_nan"].sum() == 0, (
            "该用例只验证 ranges[base].warmup_bars 禁开仓，不应依赖 has_leading_nan"
        )
        assert signals["entry_long"][:warmup_bars].sum() == 0, (
            "预热区 entry_long 必须由信号模块按 base warmup 统一置为 false"
        )
