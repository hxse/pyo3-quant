use super::frame_utils::vstack_dfs_strict;
use crate::backtest_engine::backtester::BacktestParamSegment;
use crate::backtest_engine::indicators::atr::{atr_eager, ATRConfig};
use crate::backtest_engine::walk_forward::window_runner::CompletedWindow;
use crate::error::{OptimizerError, QuantError};
use crate::types::DataPack;
use polars::prelude::*;
use std::collections::{HashMap, HashSet};

pub(super) fn build_stitched_signals(
    completed_windows: &[CompletedWindow],
) -> Result<DataFrame, QuantError> {
    let mut frames = Vec::with_capacity(completed_windows.len());
    let mut expected_start: Option<usize> = None;

    for (idx, window) in completed_windows.iter().enumerate() {
        let signals = window.test_active_result.signals.as_ref().ok_or_else(|| {
            OptimizerError::SamplingFailed(format!(
                "window {} missing active test signals",
                window.public_artifact.meta.window_id
            ))
        })?;
        let expected_len = window.public_artifact.meta.test_active_base_row_range.1
            - window.public_artifact.meta.test_active_base_row_range.0;
        if signals.height() != expected_len {
            return Err(OptimizerError::InvalidConfig(format!(
                "window {} signals.height()={} 必须等于 test_len={}",
                window.public_artifact.meta.window_id,
                signals.height(),
                expected_len
            ))
            .into());
        }
        if let Some(prev_end) = expected_start {
            if window.public_artifact.meta.test_active_base_row_range.0 != prev_end {
                return Err(OptimizerError::InvalidConfig(format!(
                    "stitched_signals 只允许拼接连续 test_range: idx={}, start={}, expected={}",
                    idx, window.public_artifact.meta.test_active_base_row_range.0, prev_end
                ))
                .into());
            }
        }
        expected_start = Some(window.public_artifact.meta.test_active_base_row_range.1);
        frames.push(signals.clone());
    }

    vstack_dfs_strict(&frames, "stitched_signals")
}

pub(super) fn build_backtest_schedule(
    completed_windows: &[CompletedWindow],
    stitched_start: usize,
) -> Result<Vec<BacktestParamSegment>, QuantError> {
    let mut schedule = Vec::with_capacity(completed_windows.len());
    let mut expected_start = 0usize;

    for (idx, window) in completed_windows.iter().enumerate() {
        let original_start = window.public_artifact.meta.test_active_base_row_range.0;
        let original_end = window.public_artifact.meta.test_active_base_row_range.1;
        if original_end <= original_start {
            return Err(OptimizerError::InvalidConfig(format!(
                "window {} test_range 非法: {:?}",
                window.public_artifact.meta.window_id,
                window.public_artifact.meta.test_active_base_row_range
            ))
            .into());
        }

        let start_row = original_start.checked_sub(stitched_start).ok_or_else(|| {
            OptimizerError::InvalidConfig(format!(
                "window {} test_range.start 小于 stitched_start",
                window.public_artifact.meta.window_id
            ))
        })?;
        let end_row = original_end.checked_sub(stitched_start).ok_or_else(|| {
            OptimizerError::InvalidConfig(format!(
                "window {} test_range.end 小于 stitched_start",
                window.public_artifact.meta.window_id
            ))
        })?;

        if start_row != expected_start {
            return Err(OptimizerError::InvalidConfig(format!(
                "backtest_schedule 非连续: idx={}, start_row={}, expected_start={}",
                idx, start_row, expected_start
            ))
            .into());
        }

        schedule.push(BacktestParamSegment::new(
            start_row,
            end_row,
            window.public_artifact.meta.best_params.backtest.clone(),
        ));
        expected_start = end_row;
    }

    Ok(schedule)
}

pub(super) fn validate_schedule_lengths(
    schedule: &[BacktestParamSegment],
    stitched_signals: &DataFrame,
    stitched_data: &DataPack,
) -> Result<(), QuantError> {
    let last_end_row = schedule
        .last()
        .map(|segment| segment.end_row)
        .ok_or_else(|| OptimizerError::InvalidConfig("stitched backtest_schedule 为空".into()))?;
    if last_end_row != stitched_signals.height() {
        return Err(OptimizerError::InvalidConfig(format!(
            "backtest_schedule 与 stitched_signals 长度不一致: schedule={}, signals={}",
            last_end_row,
            stitched_signals.height()
        ))
        .into());
    }
    if last_end_row != stitched_data.mapping.height() {
        return Err(OptimizerError::InvalidConfig(format!(
            "backtest_schedule 与 stitched_data.mapping 长度不一致: schedule={}, mapping={}",
            last_end_row,
            stitched_data.mapping.height()
        ))
        .into());
    }
    Ok(())
}

pub(super) fn build_stitched_atr_by_row(
    data_pack: &DataPack,
    stitched_start: usize,
    stitched_end: usize,
    schedule: &[BacktestParamSegment],
) -> Result<Option<Series>, QuantError> {
    let mut resolved_periods = Vec::with_capacity(schedule.len());
    let mut unique_periods = HashSet::new();
    let mut max_exec_warmup = 0usize;

    for segment in schedule {
        if segment.params.validate_atr_consistency()? {
            let period = segment
                .params
                .atr_period
                .as_ref()
                .ok_or_else(|| OptimizerError::InvalidConfig("ATR 段缺少 atr_period".into()))?
                .value as i64;
            if period <= 0 {
                return Err(
                    OptimizerError::InvalidConfig(format!("ATR period 非法: {}", period)).into(),
                );
            }
            unique_periods.insert(period);
            max_exec_warmup = max_exec_warmup.max(period as usize);
            resolved_periods.push(Some(period));
        } else {
            resolved_periods.push(None);
        }
    }

    if unique_periods.is_empty() {
        return Ok(None);
    }

    let atr_context_start = stitched_start.saturating_sub(max_exec_warmup);
    let atr_context_len = stitched_end - atr_context_start;
    let atr_context_offset = stitched_start - atr_context_start;

    let base_df = data_pack
        .source
        .get(&data_pack.base_data_key)
        .ok_or_else(|| OptimizerError::NoData)?;
    let base_ohlcv = base_df
        .slice(atr_context_start as i64, atr_context_len)
        .select(["high", "low", "close"])?;

    let mut atr_cache = HashMap::new();
    for period in unique_periods {
        let mut series = atr_eager(&base_ohlcv, &ATRConfig::new(period))?;
        series.rename("atr".into());
        atr_cache.insert(period, series);
    }

    let mut pieces = Vec::with_capacity(schedule.len());
    for (segment, resolved_period) in schedule.iter().zip(resolved_periods) {
        let segment_len = segment.end_row - segment.start_row;
        let mut piece = match resolved_period {
            Some(period) => atr_cache
                .get(&period)
                .ok_or_else(|| {
                    OptimizerError::InvalidConfig(format!("ATR cache 缺少 period={period}"))
                })?
                .slice((atr_context_offset + segment.start_row) as i64, segment_len),
            None => Series::new("atr".into(), vec![None::<f64>; segment_len]),
        };
        piece.rename("atr".into());
        pieces.push(DataFrame::new(vec![piece.into()])?);
    }

    let stitched_atr = vstack_dfs_strict(&pieces, "stitched_atr_by_row")?;
    Ok(Some(
        stitched_atr.column("atr")?.as_materialized_series().clone(),
    ))
}
