use crate::error::QuantError;
use crate::types::{BacktestParams, DataPack};
use polars::prelude::*;
use pyo3::prelude::*;
mod atr_calculator;
mod data_preparer;
mod main_loop;
mod output;
mod output_schema;
mod params_selector;
mod schedule_contract;
mod schedule_policy;
mod signal_preprocessor;
pub mod state;

use self::output_schema::build_schedule_output_schema;
use self::params_selector::build_schedule_params_selector;
pub use self::schedule_contract::BacktestParamSegment;
use self::schedule_contract::{validate_schedule_atr_contract, validate_schedule_contiguity};
use self::schedule_policy::validate_backtest_param_schedule_policy;
use crate::backtest_engine::utils::get_ohlcv_dataframe;
pub use state::frame_state::py_frame_state_name;
use {
    atr_calculator::calculate_atr_if_needed,
    data_preparer::PreparedData,
    main_loop::{legacy_run_main_loop, run_backtest_kernel},
    pyo3_polars::PyDataFrame,
};

/// 执行回测计算
///
/// 这是标准的回测入口函数，用于从零开始执行回测。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略配置
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 完整的回测结果DataFrame
pub fn legacy_run_backtest(
    processed_data: &DataPack,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    // 1. 验证参数有效性
    backtest_params.validate().map_err(QuantError::Backtest)?;

    // 2. 获取 OHLCV DataFrame 并计算 ATR（如果需要）
    let ohlcv = get_ohlcv_dataframe(processed_data)?;
    let atr_series = calculate_atr_if_needed(ohlcv, backtest_params)?;

    // 3. 准备数据，将 Polars DataFrame/Series 转换为连续的内存数组切片
    let prepared_data = PreparedData::new(processed_data, signals_df.clone(), atr_series.as_ref())?;

    // 4. 运行回测主循环
    let output_buffers = legacy_run_main_loop(prepared_data, backtest_params)?;

    // 5. 验证所有数组的长度是否相等
    output_buffers.validate_array_lengths()?;

    // 6. 将 OutputBuffers 转换为 DataFrame
    let mut result_df = output_buffers.to_dataframe()?;

    // 7. 如果信号中存在 has_leading_nan 列，将其复制到结果中
    if let Ok(col) = signals_df.column("has_leading_nan") {
        result_df.with_column(col.clone())?;
    }

    Ok(result_df)
}
/// 执行回测计算
///
/// 这是标准的回测入口函数，用于从零开始执行回测。
///
/// # 参数
/// * `processed_data` - 处理后的市场数据 DataPack，包含 OHLCV 等 source 数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略配置
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 完整的回测结果DataFrame
pub fn run_backtest(
    processed_data: &DataPack,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    backtest_params.validate().map_err(QuantError::Backtest)?;
    let ohlcv = get_ohlcv_dataframe(processed_data)?;
    let atr_series = calculate_atr_if_needed(ohlcv, backtest_params)?;
    let data_length = processed_data.mapping.height();
    let schedule = vec![BacktestParamSegment::new(
        0,
        data_length,
        backtest_params.clone(),
    )];
    run_backtest_with_schedule(processed_data, signals_df, atr_series.as_ref(), &schedule)
}

/// 执行带 schedule 的回测计算
pub fn run_backtest_with_schedule(
    processed_data: &DataPack,
    signals_df: &DataFrame,
    atr_by_row: Option<&Series>,
    schedule: &[BacktestParamSegment],
) -> Result<DataFrame, QuantError> {
    let data_length = processed_data.mapping.height();
    validate_schedule_contiguity(schedule, data_length)?;
    for segment in schedule {
        segment.params.validate().map_err(QuantError::Backtest)?;
    }
    validate_backtest_param_schedule_policy(schedule)?;
    validate_schedule_atr_contract(schedule, atr_by_row, data_length)?;

    let prepared_data = PreparedData::new(processed_data, signals_df.clone(), atr_by_row)?;
    let params_selector = build_schedule_params_selector(schedule);
    let output_schema = build_schedule_output_schema(schedule);
    let output_buffers = run_backtest_kernel(prepared_data, params_selector, output_schema)
        .map_err(QuantError::Backtest)?;

    output_buffers.validate_array_lengths()?;
    let result_df = output_buffers.to_dataframe()?;

    Ok(result_df)
}

use pyo3::IntoPyObject;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyfunction(module = "pyo3_quant.backtest_engine.backtester")]
#[pyfunction(name = "run_backtest")]
/// Python绑定：执行标准回测计算
///
/// 对应Rust函数：[`run_backtest`]
pub fn py_run_backtest(
    py: Python<'_>,
    processed_data: DataPack,
    signals_df_py: Py<PyAny>,
    backtest_params: BacktestParams,
) -> PyResult<Py<PyAny>> {
    // 从 PyObject 提取 signals_df
    let signals_df_bound = signals_df_py.bind(py);
    let signals_df: PyDataFrame = signals_df_bound.extract()?;
    let signals_df: DataFrame = signals_df.into();

    // 调用Rust回测函数并处理错误
    let result_df = run_backtest(&processed_data, &signals_df, &backtest_params)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}", e)))?;

    // 转换为Python DataFrame并返回
    let py_obj = PyDataFrame(result_df).into_pyobject(py).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Failed to convert DataFrame: {}",
            e
        ))
    })?;
    Ok(py_obj.into_any().unbind())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{Param, ParamType, SourceRange};
    use std::collections::HashMap;

    fn build_test_pack() -> DataPack {
        let times = (1..=120).map(|i| i as i64 * 1_000).collect::<Vec<_>>();
        let height = times.len();
        let open = (0..height)
            .map(|i| 100.0 + i as f64 * 0.35 + (i % 5) as f64 * 0.07)
            .collect::<Vec<_>>();
        let high = open
            .iter()
            .enumerate()
            .map(|(i, value)| value + 0.45 + (i % 3) as f64 * 0.04)
            .collect::<Vec<_>>();
        let low = open
            .iter()
            .enumerate()
            .map(|(i, value)| value - 0.40 - (i % 4) as f64 * 0.03)
            .collect::<Vec<_>>();
        let close = open
            .iter()
            .enumerate()
            .map(|(i, value)| value + 0.12 + (i % 2) as f64 * 0.05)
            .collect::<Vec<_>>();
        let ohlcv = DataFrame::new(vec![
            Series::new("time".into(), times.clone()).into(),
            Series::new("open".into(), open).into(),
            Series::new("high".into(), high).into(),
            Series::new("low".into(), low).into(),
            Series::new("close".into(), close).into(),
            Series::new("volume".into(), vec![100.0; height]).into(),
        ])
        .expect("ohlcv df 应成功");

        let source = HashMap::from([("ohlcv_1m".to_string(), ohlcv)]);
        let mapping =
            DataFrame::new(vec![Series::new("time".into(), times).into()]).expect("mapping 应成功");
        let ranges = HashMap::from([("ohlcv_1m".to_string(), SourceRange::new(0, height, height))]);
        DataPack::new_checked(source, mapping, None, "ohlcv_1m".to_string(), ranges)
    }

    fn build_test_signals() -> DataFrame {
        let mut entry_long = vec![false; 120];
        let mut exit_long = vec![false; 120];
        // 中文注释：把 10 笔交易都放到 ATR 预热之后，避免前导 NaN 把测试整段屏蔽。
        for trade_idx in 0..10 {
            let entry_idx = 30 + trade_idx * 8;
            let exit_idx = entry_idx + 4;
            entry_long[entry_idx] = true;
            exit_long[exit_idx] = true;
        }
        DataFrame::new(vec![
            Series::new("entry_long".into(), entry_long).into(),
            Series::new("exit_long".into(), exit_long).into(),
            Series::new("entry_short".into(), vec![false; 120]).into(),
            Series::new("exit_short".into(), vec![false; 120]).into(),
        ])
        .expect("signals df 应成功")
    }

    fn assert_has_completed_long_trades(df: &DataFrame, min_trades: usize) {
        let entry_long = df
            .column("entry_long_price")
            .expect("entry_long_price 列应存在")
            .f64()
            .expect("entry_long_price 必须是 f64");
        let exit_long = df
            .column("exit_long_price")
            .expect("exit_long_price 列应存在")
            .f64()
            .expect("exit_long_price 必须是 f64");

        let entry_count = entry_long
            .into_iter()
            .flatten()
            .filter(|value| !value.is_nan())
            .count();
        let exit_count = exit_long
            .into_iter()
            .flatten()
            .filter(|value| !value.is_nan())
            .count();

        assert!(
            entry_count >= min_trades,
            "测试数据必须至少产生 {} 次多头进场，当前为 {}",
            min_trades,
            entry_count
        );
        assert!(
            exit_count >= min_trades,
            "测试数据必须至少产生 {} 次多头离场，当前为 {}",
            min_trades,
            exit_count
        );
    }

    fn assert_dataframes_equal(left: &DataFrame, right: &DataFrame) {
        assert_eq!(left.height(), right.height(), "DataFrame 高度必须一致");
        assert_eq!(
            left.get_column_names(),
            right.get_column_names(),
            "DataFrame 列顺序必须一致"
        );
        assert_eq!(left.dtypes(), right.dtypes(), "DataFrame dtype 必须一致");

        for name in left.get_column_names() {
            let left_series = left
                .column(name.as_str())
                .expect("left column 应存在")
                .as_materialized_series();
            let right_series = right
                .column(name.as_str())
                .expect("right column 应存在")
                .as_materialized_series();
            assert!(
                left_series.equals_missing(right_series),
                "列 '{}' 的值必须逐项一致",
                name.as_str()
            );
        }
    }

    fn atr_params() -> BacktestParams {
        let mut params = BacktestParams::default();
        params.sl_atr = Some(Param::new(
            1.5,
            None,
            None,
            Some(ParamType::Float),
            false,
            false,
            0.01,
        ));
        params.atr_period = Some(Param::new(
            3.0,
            None,
            None,
            Some(ParamType::Integer),
            false,
            false,
            1.0,
        ));
        params
    }

    #[test]
    fn test_legacy_run_backtest_matches_run_backtest_default_contract() {
        let pack = build_test_pack();
        let signals = build_test_signals();
        let params = BacktestParams::default();

        let legacy = legacy_run_backtest(&pack, &signals, &params).expect("legacy 回测应成功");
        let current = run_backtest(&pack, &signals, &params).expect("新回测应成功");

        assert_has_completed_long_trades(&legacy, 10);
        assert_dataframes_equal(&legacy, &current);
    }

    #[test]
    fn test_legacy_run_backtest_matches_run_backtest_atr_contract() {
        let pack = build_test_pack();
        let signals = build_test_signals();
        let params = atr_params();

        let legacy = legacy_run_backtest(&pack, &signals, &params).expect("legacy 回测应成功");
        let current = run_backtest(&pack, &signals, &params).expect("新回测应成功");

        assert!(
            legacy
                .get_column_names()
                .iter()
                .any(|name| name.as_str() == "atr"),
            "ATR case 必须包含 atr 列"
        );
        assert!(
            legacy
                .get_column_names()
                .iter()
                .any(|name| name.as_str() == "sl_atr_price_long"),
            "ATR case 必须包含 sl_atr_price_long 列"
        );
        assert_has_completed_long_trades(&legacy, 10);
        assert_dataframes_equal(&legacy, &current);
    }
}
