use super::frame_utils::{ensure_same_schema, first_time, last_time, nth_time};
use crate::backtest_engine::walk_forward::window_runner::CompletedWindow;
use crate::error::{OptimizerError, QuantError};
use crate::types::{DataPack, IndicatorResults};
use polars::prelude::*;
use std::collections::{HashMap, HashSet};

pub(super) fn build_stitched_indicators(
    completed_windows: &[CompletedWindow],
    stitched_data: &DataPack,
) -> Result<Option<IndicatorResults>, QuantError> {
    let indicator_keys = collect_indicator_keys(completed_windows)?;
    if indicator_keys.is_empty() {
        return Ok(None);
    }

    let mut stitched = HashMap::new();
    for source_key in indicator_keys {
        let mut frames = Vec::with_capacity(completed_windows.len());
        for (idx, window) in completed_windows.iter().enumerate() {
            let indicators = window
                .test_active_result
                .indicators
                .as_ref()
                .ok_or_else(|| {
                    OptimizerError::SamplingFailed(format!(
                        "window {} missing indicators",
                        window.public_artifact.meta.window_id
                    ))
                })?;
            let frame = indicators.get(&source_key).ok_or_else(|| {
                OptimizerError::SamplingFailed(format!(
                    "window {} indicators 缺少 key='{}'",
                    idx, source_key
                ))
            })?;
            frames.push(frame.clone());
        }

        let stitched_df = stitch_indicator_frames(&frames, &source_key)?;
        let source_time = stitched_data
            .source
            .get(&source_key)
            .ok_or_else(|| {
                OptimizerError::InvalidConfig(format!(
                    "stitched_data.source 缺少 key='{}'",
                    source_key
                ))
            })?
            .column("time")?;
        let indicator_time = stitched_df.column("time")?;
        if !source_time
            .as_materialized_series()
            .equals_missing(indicator_time.as_materialized_series())
        {
            return Err(OptimizerError::InvalidConfig(format!(
                "stitched indicators 与 stitched_data.source['{}'].time 不一致",
                source_key
            ))
            .into());
        }

        stitched.insert(source_key, stitched_df);
    }

    Ok(Some(stitched))
}

fn collect_indicator_keys(
    completed_windows: &[CompletedWindow],
) -> Result<Vec<String>, QuantError> {
    let first_keys = completed_windows
        .first()
        .and_then(|window| window.test_active_result.indicators.as_ref())
        .map(|indicators| indicators.keys().cloned().collect::<HashSet<_>>())
        .unwrap_or_default();

    for (idx, window) in completed_windows.iter().enumerate() {
        let keys = window
            .test_active_result
            .indicators
            .as_ref()
            .map(|indicators| indicators.keys().cloned().collect::<HashSet<_>>())
            .unwrap_or_default();
        if keys != first_keys {
            return Err(OptimizerError::InvalidConfig(format!(
                "window {} indicators key 集合不一致",
                idx
            ))
            .into());
        }
    }

    let mut keys = first_keys.into_iter().collect::<Vec<_>>();
    keys.sort_unstable();
    Ok(keys)
}

pub(super) fn stitch_indicator_frames(
    frames: &[DataFrame],
    source_key: &str,
) -> Result<DataFrame, QuantError> {
    let first = frames.first().ok_or_else(|| {
        OptimizerError::InvalidConfig(format!("indicators['{}'] 为空", source_key))
    })?;
    let mut out = first.clone();

    for (idx, next) in frames.iter().enumerate().skip(1) {
        ensure_same_schema(&out, next, &format!("indicators['{}']", source_key))?;
        let out_last = last_time(&out, &format!("indicators['{}']", source_key))?;
        let next_first = first_time(next, &format!("indicators['{}']", source_key))?;

        if next_first > out_last {
            out.vstack_mut(next)?;
            continue;
        }
        if next_first < out_last {
            return Err(OptimizerError::InvalidConfig(format!(
                "stitched indicators 时间倒退: key='{}', idx={}, next_first={}, current_last={}",
                source_key, idx, next_first, out_last
            ))
            .into());
        }

        if next.height() > 1 {
            let second = nth_time(next, 1, &format!("indicators['{}']", source_key))?;
            if second <= out_last {
                return Err(OptimizerError::InvalidConfig(format!(
                    "stitched indicators 重叠超过 1 根: key='{}', idx={}",
                    source_key, idx
                ))
                .into());
            }
        }

        let mut trimmed = out.slice(0, out.height().saturating_sub(1));
        trimmed.vstack_mut(next)?;
        out = trimmed;
    }

    Ok(out)
}
