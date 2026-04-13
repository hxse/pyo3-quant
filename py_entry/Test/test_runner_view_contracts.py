from __future__ import annotations

from typing import cast
from types import SimpleNamespace

import polars as pl
import pyo3_quant
import pytest

from py_entry.Test.shared import (
    TEST_START_TIME_MS,
    make_backtest_runner,
    make_engine_settings,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.runner import BatchBacktestView
from py_entry.runner import OptimizationView
from py_entry.runner import OptunaOptimizationView
from py_entry.runner import RunnerSession
from py_entry.runner import SensitivityView
from py_entry.runner import SingleBacktestView
from py_entry.runner import WalkForwardView
from py_entry.runner.results.optuna_optimization_view import OptunaOptimizationRaw
from py_entry.types import ArtifactRetention, ExecutionStage, LogicOp, OptimizeMetric
from py_entry.types import OptimizationResult, Param
from py_entry.types import SensitivityResult, SettingContainer, SignalGroup
from py_entry.types import SignalTemplate
from py_entry.types import WalkForwardResult
from py_entry.types import OptimizerConfig, OptunaConfig, SensitivityConfig
from py_entry.types import WalkForwardConfig


def _make_contract_backtest() -> Backtest:
    """构造最小 Backtest 门面，用于返回类型契约测试。"""
    return make_backtest_runner(
        data_source=DataGenerationParams(
            timeframes=["15m"],
            start_time=TEST_START_TIME_MS,
            num_bars=120,
            fixed_seed=11,
            base_data_key="ohlcv_15m",
        ),
        indicators={
            "ohlcv_15m": {
                "sma_fast": {"period": Param(5)},
                "sma_slow": {"period": Param(10)},
            }
        },
        signal={},
        signal_template=SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
            )
        ),
        engine_settings=make_engine_settings(),
        enable_timing=False,
    )


def _make_optuna_contract_backtest() -> Backtest:
    """构造带 optimizable 参数的 Backtest 门面，用于 Optuna 契约测试。"""
    return make_backtest_runner(
        data_source=DataGenerationParams(
            timeframes=["15m"],
            start_time=TEST_START_TIME_MS,
            num_bars=120,
            fixed_seed=11,
            base_data_key="ohlcv_15m",
        ),
        indicators={
            "ohlcv_15m": {
                "sma_fast": {
                    "period": Param(
                        value=5,
                        optimize=True,
                        min=3,
                        max=7,
                        step=1,
                    )
                },
                "sma_slow": {"period": Param(10)},
            }
        },
        signal={},
        signal_template=SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
            )
        ),
        engine_settings=make_engine_settings(),
        enable_timing=False,
    )


def _build_fake_walk_forward_raw(single_view: SingleBacktestView) -> SimpleNamespace:
    """构造最小 WalkForwardView raw，用于 view contract。"""
    segment = SimpleNamespace(
        start_row=0,
        end_row=single_view.raw.mapping.height,
        params=single_view.params.backtest,
    )
    next_hint = SimpleNamespace(
        expected_window_switch_time_ms=TEST_START_TIME_MS,
        eta_days=1.5,
        based_on_window_id=0,
    )
    stitched_meta = SimpleNamespace(
        stitched_pack_time_range_from_active=(
            TEST_START_TIME_MS,
            TEST_START_TIME_MS + 1,
        ),
        next_window_hint=next_hint,
        backtest_schedule=[segment],
    )
    window_meta = SimpleNamespace(
        window_id=0,
        test_active_base_row_range=(0, single_view.raw.mapping.height),
        train_warmup_time_range=None,
        train_active_time_range=(TEST_START_TIME_MS, TEST_START_TIME_MS + 1),
        train_pack_time_range=(TEST_START_TIME_MS, TEST_START_TIME_MS + 1),
        test_warmup_time_range=(TEST_START_TIME_MS, TEST_START_TIME_MS + 1),
        test_active_time_range=(TEST_START_TIME_MS, TEST_START_TIME_MS + 1),
        test_pack_time_range=(TEST_START_TIME_MS, TEST_START_TIME_MS + 1),
        has_cross_boundary_position=False,
    )
    window_artifact = SimpleNamespace(
        meta=window_meta,
        test_pack_result=single_view.raw,
    )
    stitched_result = SimpleNamespace(
        stitched_data=single_view.session.data_pack,
        result=single_view.raw,
        meta=stitched_meta,
    )
    return SimpleNamespace(
        stitched_result=stitched_result,
        window_results=[window_artifact],
        optimize_metric=OptimizeMetric.CalmarRatioRaw,
    )


def _build_fake_optimization_raw(single_view: SingleBacktestView) -> SimpleNamespace:
    """构造最小 OptimizationView raw，用于 view contract。"""
    return SimpleNamespace(
        best_params=single_view.params,
        history=[],
        total_samples=1,
        rounds=1,
        metrics={"total_return": 1.0},
        optimize_metric=OptimizeMetric.CalmarRatioRaw,
        optimize_value=1.0,
    )


def _build_fake_sensitivity_raw() -> SimpleNamespace:
    """构造最小 SensitivityView raw，用于 view contract。"""
    return SimpleNamespace(
        target_metric="calmar_ratio_raw",
        samples=[],
        total_samples_requested=1,
        successful_samples=1,
        failed_samples=0,
        original_value=1.0,
        failed_sample_rate=0.0,
        mean=1.0,
        std=0.0,
        p05=1.0,
        p25=1.0,
        median=1.0,
        p75=1.0,
        p95=1.0,
        min=1.0,
        max=1.0,
        cv=0.0,
    )


def _assert_performance_settings(
    settings: SettingContainer,
    artifact_retention: ArtifactRetention,
) -> None:
    """断言 Python runner 已编译为 Rust mode 要求的正式执行设置。"""
    assert settings.stop_stage == ExecutionStage.Performance
    assert settings.artifact_retention == artifact_retention


def test_backtest_methods_return_formal_views(monkeypatch):
    """Backtest.*() 必须返回正式 *View 对象。"""
    bt = _make_contract_backtest()
    single = bt.run()
    assert isinstance(single, SingleBacktestView)
    assert isinstance(single.session, RunnerSession)

    monkeypatch.setattr(
        pyo3_quant.backtest_engine,
        "run_batch_backtest",
        lambda data, params, template, engine_settings: [single.raw for _ in params],
    )
    batch = bt.batch([bt.params, bt.params])
    assert isinstance(batch, BatchBacktestView)
    assert isinstance(batch.session, RunnerSession)

    optimization_raw = SimpleNamespace(
        best_params=bt.params,
        history=[],
        total_samples=1,
        rounds=1,
        metrics={"total_return": 1.0},
        optimize_metric=OptimizeMetric.CalmarRatioRaw,
        optimize_value=1.0,
    )
    captured_settings: dict[str, SettingContainer] = {}

    def fake_optimizer(data, param, template, engine_settings, config):
        captured_settings["optimizer"] = engine_settings
        return optimization_raw

    monkeypatch.setattr(
        pyo3_quant.backtest_engine.optimizer,
        "py_run_optimizer",
        fake_optimizer,
    )
    optimization = bt.optimize(OptimizerConfig())
    assert isinstance(optimization, OptimizationView)
    assert isinstance(optimization.session, RunnerSession)
    _assert_performance_settings(
        captured_settings["optimizer"],
        ArtifactRetention.StopStageOnly,
    )
    _assert_performance_settings(
        optimization.session.engine_settings,
        ArtifactRetention.StopStageOnly,
    )

    walk_forward_raw = _build_fake_walk_forward_raw(single)

    def fake_walk_forward(data, param, template, engine_settings, config):
        captured_settings["walk_forward"] = engine_settings
        return walk_forward_raw

    monkeypatch.setattr(
        pyo3_quant.backtest_engine.walk_forward,
        "run_walk_forward",
        fake_walk_forward,
    )
    walk_forward = bt.walk_forward(
        WalkForwardConfig(train_active_bars=20, test_active_bars=10)
    )
    assert isinstance(walk_forward, WalkForwardView)
    assert isinstance(walk_forward.session, RunnerSession)
    _assert_performance_settings(
        captured_settings["walk_forward"],
        ArtifactRetention.AllCompletedStages,
    )
    _assert_performance_settings(
        walk_forward.session.engine_settings,
        ArtifactRetention.AllCompletedStages,
    )

    sensitivity_raw = _build_fake_sensitivity_raw()

    def fake_sensitivity(data, param, template, engine_settings, config):
        captured_settings["sensitivity"] = engine_settings
        return sensitivity_raw

    monkeypatch.setattr(
        pyo3_quant.backtest_engine.sensitivity,
        "run_sensitivity_test",
        fake_sensitivity,
    )
    sensitivity = bt.sensitivity(SensitivityConfig())
    assert isinstance(sensitivity, SensitivityView)
    assert isinstance(sensitivity.session, RunnerSession)
    _assert_performance_settings(
        captured_settings["sensitivity"],
        ArtifactRetention.StopStageOnly,
    )
    _assert_performance_settings(
        sensitivity.session.engine_settings,
        ArtifactRetention.StopStageOnly,
    )

    optuna_view = OptunaOptimizationView(
        raw=OptunaOptimizationRaw(
            best_params={},
            best_signal_params={},
            best_backtest_params={},
            best_value=1.0,
            n_trials=1,
            history=[],
            study=None,
        ),
        session=bt.session,
    )
    monkeypatch.setattr(
        "py_entry.runner.optuna_optimizer.run_optuna_optimization",
        lambda backtest, config, params_override=None: optuna_view,
    )
    optuna = bt.optimize_with_optuna()
    assert isinstance(optuna, OptunaOptimizationView)
    assert isinstance(optuna.session, RunnerSession)


def test_optuna_uses_formal_mode_settings_in_batch_mode(monkeypatch):
    """Optuna batch trial 必须固定使用 performance + stop-stage-only。"""
    bt = _make_optuna_contract_backtest()
    fake_result = SimpleNamespace(performance={"calmar_ratio_raw": 1.0})
    captured_settings: list[SettingContainer] = []

    def fake_batch(data, params, template, engine_settings):
        captured_settings.append(engine_settings)
        return [fake_result for _ in params]

    monkeypatch.setattr(
        pyo3_quant.backtest_engine,
        "run_batch_backtest",
        fake_batch,
    )

    optuna = bt.optimize_with_optuna(
        OptunaConfig(n_trials=1, batch_size=1, n_jobs=1, show_progress_bar=False)
    )

    assert isinstance(optuna, OptunaOptimizationView)
    _assert_performance_settings(
        captured_settings[0],
        ArtifactRetention.StopStageOnly,
    )
    _assert_performance_settings(
        optuna.session.engine_settings,
        ArtifactRetention.StopStageOnly,
    )


def test_optuna_uses_formal_mode_settings_in_parallel_mode(monkeypatch):
    """Optuna parallel trial 必须固定使用 performance + stop-stage-only。"""
    bt = _make_optuna_contract_backtest()
    fake_result = SimpleNamespace(performance={"calmar_ratio_raw": 1.0})
    captured_settings: list[SettingContainer] = []

    def fake_single(data, param, template, engine_settings):
        captured_settings.append(engine_settings)
        return fake_result

    monkeypatch.setattr(
        pyo3_quant.backtest_engine,
        "run_single_backtest",
        fake_single,
    )

    optuna = bt.optimize_with_optuna(
        OptunaConfig(n_trials=1, n_jobs=2, show_progress_bar=False)
    )

    assert isinstance(optuna, OptunaOptimizationView)
    _assert_performance_settings(
        captured_settings[0],
        ArtifactRetention.StopStageOnly,
    )
    _assert_performance_settings(
        optuna.session.engine_settings,
        ArtifactRetention.StopStageOnly,
    )


def test_runner_session_engine_settings_is_execution_snapshot():
    """view.session.engine_settings 必须是执行时快照，不受后续 mutation 污染。"""
    bt = _make_contract_backtest()
    single = bt.run()
    session_settings = single.session.engine_settings

    bt.engine_settings.artifact_retention = ArtifactRetention.StopStageOnly

    assert session_settings is not bt.engine_settings
    _assert_performance_settings(
        session_settings,
        ArtifactRetention.AllCompletedStages,
    )


def test_view_and_bundle_contracts(capsys):
    """正式 view / bundle 契约必须覆盖 session、report 与导出边界。"""
    bt = _make_contract_backtest()
    single = bt.run()
    fake_walk_forward_raw = _build_fake_walk_forward_raw(single)

    walk_forward = WalkForwardView(
        raw=cast(WalkForwardResult, fake_walk_forward_raw),
        session=single.session,
    )
    batch = BatchBacktestView(items=[single], session=single.session)
    optimization = OptimizationView(
        raw=cast(OptimizationResult, _build_fake_optimization_raw(single)),
        session=single.session,
    )
    sensitivity = SensitivityView(
        raw=cast(SensitivityResult, _build_fake_sensitivity_raw()),
        session=single.session,
    )
    optuna = OptunaOptimizationView(
        raw=OptunaOptimizationRaw(
            best_params={},
            best_signal_params={},
            best_backtest_params={},
            best_value=1.0,
            n_trials=1,
            history=[],
            study=None,
        ),
        session=single.session,
    )

    assert isinstance(single.session, RunnerSession)
    assert isinstance(batch.session, RunnerSession)
    assert isinstance(walk_forward.session, RunnerSession)
    assert isinstance(optimization.session, RunnerSession)
    assert isinstance(sensitivity.session, RunnerSession)
    assert isinstance(optuna.session, RunnerSession)

    assert callable(single.prepare_export)
    assert callable(walk_forward.prepare_export)
    assert not hasattr(batch, "prepare_export")
    assert not hasattr(optimization, "prepare_export")
    assert not hasattr(sensitivity, "prepare_export")
    assert not hasattr(optuna, "prepare_export")

    assert single.build_report()["stage"] == "backtest"
    assert batch.build_report()["stage"] == "batch"
    assert walk_forward.build_report()["stage"] == "walk_forward"
    assert optimization.build_report()["stage"] == "optimize"
    assert sensitivity.build_report()["stage"] == "sensitivity"
    assert optuna.build_report()["stage"] == "optuna_optimize"

    single.print_report()
    batch.print_report()
    walk_forward.print_report()
    optimization.print_report()
    sensitivity.print_report()
    optuna.print_report()
    out = capsys.readouterr().out
    assert "backtest" in out
    assert "walk_forward" in out
    assert "optuna_optimize" in out


def test_walk_forward_stitched_equity_rejects_missing_equity_column():
    """stitched_equity 只允许无 backtest_df，不允许静默吞掉 schema 漂移。"""
    bt = _make_contract_backtest()
    single = bt.run()
    fake_walk_forward_raw = _build_fake_walk_forward_raw(single)
    fake_walk_forward_raw.stitched_result.result = SimpleNamespace(
        backtest_result=pl.DataFrame({"time": [1, 2]}),
        performance={},
    )
    walk_forward = WalkForwardView(
        raw=cast(WalkForwardResult, fake_walk_forward_raw),
        session=single.session,
    )

    with pytest.raises(KeyError, match="equity"):
        _ = walk_forward.stitched_equity
