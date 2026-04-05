import pyo3_quant
import polars as pl
from py_entry.Test.indicators.conftest import run_indicator_backtest
from py_entry.Test.shared.constants import TEST_START_TIME_MS
from py_entry.data_generator import DataGenerationParams
from py_entry.types import Param


def _indicator_output_columns(indicators_df, indicator_key: str) -> list[str]:
    """按全列口径返回指标输出列。"""
    # 中文注释：测试口径与运行时保持一致，使用该指标实例全部输出列断言。
    return [c for c in indicators_df.columns if c.startswith(indicator_key)]


def _missing_expr(col_name: str) -> pl.Expr:
    """统一缺失表达式（null 或 NaN）。"""
    col = pl.col(col_name).cast(pl.Float64, strict=False)
    return col.is_null() | col.is_nan()


def _leading_missing_count(indicators_df, col: str) -> int:
    """计算单列前导空值数量（Polars 向量化）。"""
    missing_mask = (
        indicators_df.select(_missing_expr(col).alias("__missing"))
        .get_column("__missing")
        .cast(pl.Boolean, strict=False)
    )
    if missing_mask.len() == 0:
        return 0
    if bool(missing_mask.all()):
        return int(missing_mask.len())
    return int(missing_mask.arg_min())


def _assert_warmup_contract(indicators_df, cols: list[str], warmup: int, mode: str):
    """执行单指标 warmup 合约断言。"""
    if not cols:
        raise AssertionError("未找到目标指标输出列，无法执行 warmup 校验。")

    rows = indicators_df.height
    assert 0 <= warmup <= rows

    # 中文注释：全列口径下，warmup 必须等于“各列前导空值数量”的最大值。
    observed_warmup = max(_leading_missing_count(indicators_df, col) for col in cols)
    assert observed_warmup == warmup, (
        f"warmup 不匹配: required={warmup}, observed={observed_warmup}"
    )

    # 非预热段按模式校验。
    if warmup >= rows:
        return

    data_slice = indicators_df.slice(warmup, rows - warmup)
    if mode == "Strict":
        missing_counts_df = data_slice.select(
            [_missing_expr(col).sum().alias(col) for col in cols]
        )
        bad_cols = [col for col in cols if int(missing_counts_df[col][0] or 0) > 0]
        if bad_cols:
            bad_col = bad_cols[0]
            missing_mask = (
                data_slice.select(_missing_expr(bad_col).alias("__missing"))
                .get_column("__missing")
                .cast(pl.Boolean, strict=False)
            )
            first_bad_row = int(missing_mask.arg_max())
            raise AssertionError(
                f"非预热段存在空值: row={warmup + first_bad_row}, col={bad_col}"
            )
    else:
        # 中文注释：Relaxed 允许结构性空值，但每一行都不能“整行全空”。
        row_all_missing = (
            data_slice.select(
                pl.all_horizontal([_missing_expr(col) for col in cols]).alias(
                    "__row_all_missing"
                )
            )
            .get_column("__row_all_missing")
            .cast(pl.Boolean, strict=False)
        )
        if bool(row_all_missing.any()):
            bad_row = warmup + int(row_all_missing.arg_max())
            raise AssertionError(f"Relaxed 模式下非预热段不允许整行全空: row={bad_row}")


def test_indicator_warmup_contract(data_params):
    """单指标逐一校验 required_warmup_bars 与 warmup_mode 契约。"""
    cases = [
        ("sma", {"period": Param(14)}, 13, "Strict"),
        ("ema", {"period": Param(14)}, 13, "Strict"),
        ("rma", {"period": Param(14)}, 0, "Strict"),
        ("rsi", {"period": Param(14)}, 14, "Strict"),
        ("tr", {}, 1, "Strict"),
        ("atr", {"period": Param(14)}, 14, "Strict"),
        (
            "macd",
            {
                "fast_period": Param(12),
                "slow_period": Param(26),
                "signal_period": Param(9),
            },
            33,
            "Strict",
        ),
        ("adx", {"period": Param(14), "adxr_length": Param(2)}, 29, "Strict"),
        ("cci", {"period": Param(14)}, 13, "Strict"),
        ("bbands", {"period": Param(20), "std": Param(2.0)}, 19, "Strict"),
        ("er", {"length": Param(10)}, 10, "Strict"),
        (
            "psar",
            {"af0": Param(0.02), "af_step": Param(0.02), "max_af": Param(0.2)},
            2,
            "Relaxed",
        ),
        ("opening-bar", {"threshold": Param(3600)}, 0, "Strict"),
        ("sma-close-pct", {"period": Param(14)}, 13, "Strict"),
        ("cci-divergence", {"period": Param(14), "window": Param(10)}, 13, "Strict"),
        ("rsi-divergence", {"period": Param(14), "window": Param(10)}, 14, "Strict"),
        (
            "macd-divergence",
            {
                "fast_period": Param(12),
                "slow_period": Param(26),
                "signal_period": Param(9),
                "window": Param(10),
            },
            33,
            "Strict",
        ),
    ]

    for idx, (base_name, params, expected_warmup, expected_mode) in enumerate(cases):
        indicator_key = f"{base_name}_{idx}"
        indicators_params = {"ohlcv_15m": {indicator_key: params}}

        # 1) 先校验静态契约聚合结果。
        report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            indicators_params
        )
        contract = report.contracts_by_indicator[f"ohlcv_15m::{indicator_key}"]
        assert contract.warmup_bars == expected_warmup
        assert contract.warmup_mode == expected_mode

        # 2) 再校验运行时输出是否满足对应模式。
        backtest_results, _ = run_indicator_backtest(data_params, indicators_params)
        summary = backtest_results[0]
        assert summary.indicators is not None
        indicators_df = summary.indicators["ohlcv_15m"]

        monitored_cols = _indicator_output_columns(indicators_df, indicator_key)
        _assert_warmup_contract(
            indicators_df,
            monitored_cols,
            contract.warmup_bars,
            contract.warmup_mode,
        )


def test_indicator_warmup_scaling_scan():
    """参数化扫描：校验 warmup 随参数放大而单调增长。"""
    # 中文注释：重点覆盖 period=1 的边界，防止 saturating_sub 在极值下静默归零。
    scaling_cases = [
        ("sma", "period", [1, 5, 50, 200]),
        ("ema", "period", [1, 5, 50, 200]),
        ("cci", "period", [1, 5, 50, 200]),
        ("bbands", "period", [1, 5, 50, 200]),
        ("sma-close-pct", "period", [1, 5, 50, 200]),
        ("atr", "period", [1, 14, 50, 100]),
        ("rsi", "period", [1, 14, 50, 100]),
    ]

    for idx, (base_name, param_name, values) in enumerate(scaling_cases):
        observed: list[int] = []
        for val in values:
            indicator_key = f"{base_name}_scan_{idx}_{val}"
            params = {param_name: Param(val)}
            if base_name == "bbands":
                params["std"] = Param(2.0)
            indicators_params = {"ohlcv_15m": {indicator_key: params}}
            report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
                indicators_params
            )
            contract = report.contracts_by_indicator[f"ohlcv_15m::{indicator_key}"]
            observed.append(int(contract.warmup_bars))

        assert observed == sorted(observed), (
            f"{base_name} warmup 随参数放大应单调不减: values={values}, observed={observed}"
        )

    # 中文注释：复合指标单独扫描，覆盖多参数场景。
    macd_obs: list[int] = []
    for slow in [12, 26, 50]:
        key = f"macd_scan_{slow}"
        params = {
            "fast_period": Param(6),
            "slow_period": Param(slow),
            "signal_period": Param(9),
        }
        report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            {"ohlcv_15m": {key: params}}
        )
        macd_obs.append(
            int(report.contracts_by_indicator[f"ohlcv_15m::{key}"].warmup_bars)
        )
    assert macd_obs == sorted(macd_obs), f"macd warmup 缩放异常: {macd_obs}"

    adx_obs: list[int] = []
    for period in [5, 14, 30]:
        key = f"adx_scan_{period}"
        params = {"period": Param(period), "adxr_length": Param(2)}
        report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            {"ohlcv_15m": {key: params}}
        )
        adx_obs.append(
            int(report.contracts_by_indicator[f"ohlcv_15m::{key}"].warmup_bars)
        )
    assert adx_obs == sorted(adx_obs), f"adx warmup 缩放异常: {adx_obs}"

    er_obs: list[int] = []
    for length in [1, 10, 50]:
        key = f"er_scan_{length}"
        params = {"length": Param(length)}
        report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
            {"ohlcv_15m": {key: params}}
        )
        er_obs.append(
            int(report.contracts_by_indicator[f"ohlcv_15m::{key}"].warmup_bars)
        )
    assert er_obs == sorted(er_obs), f"er warmup 缩放异常: {er_obs}"


def test_divergence_window_false_not_killed_by_strict():
    """Divergence 前导 false 感知：false 不应被 Strict 当作缺失值误杀。"""
    # 中文注释：使用短样本复现场景（50 行），重点看 warmup 外 window-1 的 false 输出。
    short_data = DataGenerationParams(
        timeframes=["15m"],
        start_time=TEST_START_TIME_MS,
        num_bars=50,
        base_data_key="ohlcv_15m",
        fixed_seed=11,
        allow_gaps=False,
    )

    indicator_key = "cci-divergence_short"
    indicators_params = {
        "ohlcv_15m": {
            indicator_key: {
                "period": Param(14),
                "window": Param(30),
                "gap": Param(3),
                "recency": Param(3),
            }
        }
    }

    report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
        indicators_params
    )
    contract = report.contracts_by_indicator[f"ohlcv_15m::{indicator_key}"]
    assert contract.warmup_mode == "Strict"

    backtest_results, _ = run_indicator_backtest(short_data, indicators_params)
    summary = backtest_results[0]
    assert summary.indicators is not None
    df = summary.indicators["ohlcv_15m"]

    cols = _indicator_output_columns(df, indicator_key)
    _assert_warmup_contract(
        df, cols, int(contract.warmup_bars), str(contract.warmup_mode)
    )

    # 中文注释：重点验证 warmup 外窗口前段，top/bottom 可为 false，但不应是缺失值。
    top_col = f"{indicator_key}_top"
    bottom_col = f"{indicator_key}_bottom"
    start = int(contract.warmup_bars)
    end = min(start + 29, df.height)
    seg_len = max(0, end - start)
    segment = df.slice(start, seg_len)
    top_missing = int(
        segment.select(_missing_expr(top_col).sum().alias("__m"))["__m"][0] or 0
    )
    bottom_missing = int(
        segment.select(_missing_expr(bottom_col).sum().alias("__m"))["__m"][0] or 0
    )
    assert top_missing == 0, f"top 列在区间 [{start}, {end}) 不应出现缺失"
    assert bottom_missing == 0, f"bottom 列在区间 [{start}, {end}) 不应出现缺失"
