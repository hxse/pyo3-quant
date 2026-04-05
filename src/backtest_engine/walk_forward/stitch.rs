mod frame_utils;
mod indicators;
mod replay;

use self::indicators::build_stitched_indicators;
use self::replay::{
    build_backtest_schedule, build_stitched_atr_by_row, build_stitched_signals,
    validate_schedule_lengths,
};
use crate::backtest_engine::backtester::run_backtest_with_schedule;
use crate::backtest_engine::data_ops::{
    build_result_pack, slice_data_pack_by_base_window, strip_indicator_time_columns,
};
use crate::backtest_engine::performance_analyzer::analyze_performance;
use crate::backtest_engine::walk_forward::data_splitter::{build_window_slice_indices, WindowPlan};
use crate::backtest_engine::walk_forward::next_window_hint::build_next_window_hint;
use crate::backtest_engine::walk_forward::stitched_checks::{
    assert_source_times_non_decreasing, assert_time_strictly_increasing,
};
use crate::backtest_engine::walk_forward::time_ranges::extract_base_times;
use crate::backtest_engine::walk_forward::window_runner::CompletedWindow;
use crate::error::{OptimizerError, QuantError};
use crate::types::{
    DataPack, IndicatorResults, ResultPack, StitchedArtifact, StitchedMeta, WalkForwardConfig,
};
use polars::prelude::*;

/// 中文注释：stitched 真值统一走 segmented replay，并直接回收到正式公开壳层。
pub(crate) fn build_stitched_artifact(
    data_pack: &DataPack,
    param: &crate::types::SingleParamSet,
    config: &WalkForwardConfig,
    windows: &[WindowPlan],
    completed_windows: &[CompletedWindow],
) -> Result<StitchedArtifact, QuantError> {
    validate_stitched_inputs(windows, completed_windows)?;

    let first = completed_windows
        .first()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;
    let last = completed_windows
        .last()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;

    let stitched_start = first.public_artifact.meta.test_active_base_row_range.0;
    let stitched_end = last.public_artifact.meta.test_active_base_row_range.1;

    let stitched_required = data_pack
        .source
        .keys()
        .map(|key| (key.clone(), 0_usize))
        .collect::<std::collections::HashMap<_, _>>();
    let stitched_data = slice_data_pack_by_base_window(
        data_pack,
        &build_window_slice_indices(
            data_pack,
            (stitched_start, stitched_end),
            (stitched_start, stitched_end),
            &stitched_required,
        )
        .map_err(QuantError::from)?,
    )?;
    let stitched_times = extract_base_times(&stitched_data)?;
    assert_time_strictly_increasing(&stitched_times)?;
    assert_source_times_non_decreasing(&stitched_data)?;

    let stitched_signals = build_stitched_signals(completed_windows)?;
    let backtest_schedule = build_backtest_schedule(completed_windows, stitched_start)?;
    validate_schedule_lengths(&backtest_schedule, &stitched_signals, &stitched_data)?;
    let stitched_atr_by_row =
        build_stitched_atr_by_row(data_pack, stitched_start, stitched_end, &backtest_schedule)?;
    let stitched_indicators_with_time =
        build_stitched_indicators(completed_windows, &stitched_data)?;

    let stitched_backtest = run_backtest_with_schedule(
        &stitched_data,
        &stitched_signals,
        stitched_atr_by_row.as_ref(),
        &backtest_schedule,
    )?;
    let stitched_metrics =
        analyze_performance(&stitched_data, &stitched_backtest, &param.performance)?;
    let stitched_result = build_stitched_result_pack(
        &stitched_data,
        stitched_indicators_with_time,
        stitched_signals,
        stitched_backtest,
        stitched_metrics,
    )?;
    let window_results = completed_windows
        .iter()
        .map(|window| window.public_artifact.clone())
        .collect::<Vec<_>>();
    let next_window_hint = build_next_window_hint(&window_results, config)?;
    let stitched_pack_time_range_from_active = (
        *stitched_times
            .first()
            .ok_or_else(|| OptimizerError::InvalidConfig("stitched time empty".into()))?,
        *stitched_times
            .last()
            .ok_or_else(|| OptimizerError::InvalidConfig("stitched time empty".into()))?,
    );
    let stitched_window_active_time_ranges = completed_windows
        .iter()
        .map(|window| window.public_artifact.meta.test_active_time_range)
        .collect::<Vec<_>>();

    Ok(StitchedArtifact {
        stitched_data,
        result: stitched_result,
        meta: StitchedMeta {
            window_count: windows.len(),
            stitched_pack_time_range_from_active,
            stitched_window_active_time_ranges,
            backtest_schedule,
            next_window_hint,
        },
    })
}

fn build_stitched_result_pack(
    stitched_data: &DataPack,
    stitched_indicators_with_time: Option<IndicatorResults>,
    stitched_signals: DataFrame,
    stitched_backtest: DataFrame,
    stitched_metrics: crate::types::PerformanceMetrics,
) -> Result<ResultPack, QuantError> {
    let stitched_raw_indicators = match stitched_indicators_with_time {
        Some(indicators) => Some(strip_indicator_time_columns(&indicators)?),
        None => None,
    };

    build_result_pack(
        stitched_data,
        stitched_raw_indicators,
        Some(stitched_signals),
        Some(stitched_backtest),
        Some(stitched_metrics),
    )
}

fn validate_stitched_inputs(
    windows: &[WindowPlan],
    completed_windows: &[CompletedWindow],
) -> Result<(), QuantError> {
    if windows.len() != completed_windows.len() {
        return Err(OptimizerError::InvalidConfig(format!(
            "window specs / results 长度不一致: specs={}, results={}",
            windows.len(),
            completed_windows.len()
        ))
        .into());
    }
    if windows.is_empty() {
        return Err(OptimizerError::InvalidConfig("no windows".into()).into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::indicators::stitch_indicator_frames;
    use super::replay::build_backtest_schedule;
    use crate::backtest_engine::walk_forward::window_runner::CompletedWindow;
    use crate::types::{
        DataPack, ResultPack, SingleParamSet, SourceRange, WindowArtifact, WindowMeta,
    };
    use polars::prelude::*;
    use std::collections::HashMap;

    fn dummy_signals(height: usize) -> DataFrame {
        DataFrame::new(vec![
            Series::new("time".into(), (0..height as i64).collect::<Vec<_>>()).into(),
            Series::new("signal".into(), vec![0_i8; height]).into(),
        ])
        .expect("signals 应成功")
    }

    fn dummy_pack(height: usize) -> DataPack {
        let source = HashMap::from([(
            "ohlcv_1m".to_string(),
            DataFrame::new(vec![Series::new(
                "time".into(),
                (0..height as i64).collect::<Vec<_>>(),
            )
            .into()])
            .expect("source 应成功"),
        )]);
        let mapping = DataFrame::new(vec![Series::new(
            "time".into(),
            (0..height as i64).collect::<Vec<_>>(),
        )
        .into()])
        .expect("mapping 应成功");
        DataPack::new_checked(
            source,
            mapping,
            None,
            "ohlcv_1m".to_string(),
            HashMap::from([("ohlcv_1m".to_string(), SourceRange::new(0, height, height))]),
        )
    }

    fn dummy_window(start: usize, end: usize) -> CompletedWindow {
        let height = end - start;
        let pack = dummy_pack(height);
        CompletedWindow {
            test_active_result: ResultPack::new_checked(
                None,
                Some(dummy_signals(height)),
                None,
                None,
                DataFrame::new(vec![Series::new(
                    "time".into(),
                    (0..height as i64).collect::<Vec<_>>(),
                )
                .into()])
                .expect("active mapping 应成功"),
                HashMap::from([("ohlcv_1m".to_string(), SourceRange::new(0, height, height))]),
                "ohlcv_1m".to_string(),
            ),
            public_artifact: WindowArtifact {
                train_pack_data: pack.clone(),
                test_pack_data: pack,
                test_pack_result: ResultPack::new_checked(
                    None,
                    Some(dummy_signals(height)),
                    None,
                    None,
                    DataFrame::new(vec![Series::new(
                        "time".into(),
                        (0..height as i64).collect::<Vec<_>>(),
                    )
                    .into()])
                    .expect("test mapping 应成功"),
                    HashMap::from([("ohlcv_1m".to_string(), SourceRange::new(0, height, height))]),
                    "ohlcv_1m".to_string(),
                ),
                meta: WindowMeta {
                    window_id: 0,
                    best_params: SingleParamSet::default(),
                    has_cross_boundary_position: false,
                    test_active_base_row_range: (start, end),
                    train_warmup_time_range: None,
                    train_active_time_range: (0, 0),
                    train_pack_time_range: (0, 0),
                    test_warmup_time_range: (0, 0),
                    test_active_time_range: (start as i64, (end - 1) as i64),
                    test_pack_time_range: (start as i64, (end - 1) as i64),
                },
            },
        }
    }

    #[test]
    fn test_stitched_replay_input_contract() {
        let windows = vec![
            dummy_window(10, 12),
            dummy_window(12, 15),
            dummy_window(15, 19),
        ];
        let schedule = build_backtest_schedule(&windows, 10).expect("schedule 应成功");
        assert_eq!(schedule.len(), 3);
        assert_eq!(schedule[0].start_row, 0);
        assert_eq!(schedule[0].end_row, 2);
        assert_eq!(schedule[1].start_row, 2);
        assert_eq!(schedule[1].end_row, 5);
        assert_eq!(schedule[2].start_row, 5);
        assert_eq!(schedule[2].end_row, 9);
    }

    #[test]
    fn test_stitch_indicator_single_overlap_contract() {
        let first = DataFrame::new(vec![
            Series::new("time".into(), vec![10_i64, 20, 30]).into(),
            Series::new("v".into(), vec![1_i64, 2, 3]).into(),
        ])
        .expect("first 应成功");
        let second = DataFrame::new(vec![
            Series::new("time".into(), vec![30_i64, 40]).into(),
            Series::new("v".into(), vec![30_i64, 4]).into(),
        ])
        .expect("second 应成功");

        let stitched =
            stitch_indicator_frames(&[first, second], "ohlcv_5m").expect("指标 stitched 应成功");
        assert_eq!(stitched.height(), 4);
        assert_eq!(
            stitched
                .column("time")
                .expect("time 列")
                .i64()
                .expect("time dtype")
                .into_no_null_iter()
                .collect::<Vec<_>>(),
            vec![10, 20, 30, 40]
        );
        assert_eq!(
            stitched
                .column("v")
                .expect("v 列")
                .i64()
                .expect("v dtype")
                .into_no_null_iter()
                .collect::<Vec<_>>(),
            vec![1, 2, 30, 4]
        );
    }
}
