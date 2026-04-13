use crate::backtest_engine::data_ops::{
    build_data_pack, build_result_pack, strip_indicator_time_columns,
};
use crate::backtest_engine::walk_forward::data_splitter::{
    build_window_slice_indices, WindowSliceIndices,
};
use crate::error::QuantError;
use crate::types::{DataPack, ResultPack};
use polars::prelude::*;
use std::collections::HashMap;

fn is_natural_sequence_u32(series: &UInt32Chunked) -> bool {
    if series.null_count() > 0 {
        return false;
    }
    for (i, v) in series.into_no_null_iter().enumerate() {
        if v != i as u32 {
            return false;
        }
    }
    true
}

pub fn is_natural_mapping_for_source(
    data: &DataPack,
    source_key: &str,
) -> Result<bool, QuantError> {
    let mapping_col = data.mapping.column(source_key).map_err(|_| {
        QuantError::InvalidParam(format!("mapping 中缺少 source 列 '{source_key}'"))
    })?;
    let mapping_u32 = mapping_col.u32().map_err(|_| {
        QuantError::InvalidParam(format!("mapping 列 '{source_key}' 必须为 UInt32"))
    })?;
    Ok(is_natural_sequence_u32(mapping_u32))
}

pub fn slice_data_pack_by_base_window(
    data: &DataPack,
    indices: &WindowSliceIndices,
) -> Result<DataPack, QuantError> {
    let base_range = indices
        .source_ranges
        .get(&data.base_data_key)
        .ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "WindowSliceIndices.source_ranges 缺少 base_data_key='{}'",
                data.base_data_key
            ))
        })?;
    if base_range.start >= base_range.end {
        return Err(QuantError::InvalidParam(format!(
            "base source_range 非法: [{}, {})",
            base_range.start, base_range.end
        )));
    }

    let mut source_keys: Vec<String> = indices.source_ranges.keys().cloned().collect();
    source_keys.sort_unstable();
    let mut sliced_source: HashMap<String, DataFrame> = HashMap::with_capacity(source_keys.len());

    for source_key in source_keys {
        let source_df = data
            .source
            .get(&source_key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{source_key}' 不存在")))?;
        let projected_range = indices.source_ranges.get(&source_key).ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "WindowSliceIndices.source_ranges 缺少 key='{source_key}'"
            ))
        })?;
        if projected_range.end > source_df.height() {
            return Err(QuantError::InvalidParam(format!(
                "source_ranges['{source_key}'] 越界: end={} > source height={}",
                projected_range.end,
                source_df.height()
            )));
        }
        let source_slice = source_df.slice(
            projected_range.start as i64,
            projected_range.end - projected_range.start,
        );
        sliced_source.insert(source_key.clone(), source_slice);
    }

    let sliced_skip_mask = data
        .skip_mask
        .as_ref()
        .map(|df| df.slice(base_range.start as i64, base_range.end - base_range.start));

    build_data_pack(
        sliced_source,
        data.base_data_key.clone(),
        indices.ranges_draft.clone(),
        sliced_skip_mask,
    )
}

fn validate_slice_bounds(
    height: usize,
    start: usize,
    len: usize,
    name: &str,
) -> Result<(), QuantError> {
    if len == 0 {
        return Err(QuantError::InvalidParam(format!(
            "{name} 切片长度 len 必须 > 0"
        )));
    }
    if start >= height || start + len > height {
        return Err(QuantError::InvalidParam(format!(
            "{name} 切片越界: height={height}, start={start}, len={len}"
        )));
    }
    Ok(())
}

/// 按 base 窗口切片 ResultPack（含 indicators mapping 语义切片）。
pub fn slice_result_pack_by_base_window(
    result: &ResultPack,
    data: &DataPack,
    indices: &WindowSliceIndices,
) -> Result<ResultPack, QuantError> {
    if result.base_data_key != data.base_data_key {
        return Err(QuantError::InvalidParam(format!(
            "slice_result_pack(...) 要求 ResultPack/DataPack 的 base_data_key 一致，当前 result='{}', data='{}'",
            result.base_data_key, data.base_data_key
        )));
    }
    let base_range = indices
        .source_ranges
        .get(&data.base_data_key)
        .ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "WindowSliceIndices.source_ranges 缺少 base_data_key='{}'",
                data.base_data_key
            ))
        })?;
    let start = base_range.start;
    let len = base_range.end - base_range.start;
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    validate_slice_bounds(base_df.height(), start, len, "ResultPack")?;
    let sliced_data_pack = slice_data_pack_by_base_window(data, indices)?;

    let mut indicator_keys = result
        .indicators
        .as_ref()
        .map(|map| map.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    indicator_keys.sort_unstable();

    let indicators_with_time = match &result.indicators {
        Some(ind_map) if !ind_map.is_empty() => {
            let result_indices =
                build_result_slice_indices(indices, &result.base_data_key, &indicator_keys)?;
            let mut fake_source = HashMap::with_capacity(indicator_keys.len() + 1);
            fake_source.insert(
                result.base_data_key.clone(),
                data.source[&result.base_data_key].clone(),
            );
            for source_key in &indicator_keys {
                let indicator_df = ind_map.get(source_key).ok_or_else(|| {
                    QuantError::InvalidParam(format!("result.indicators 缺少 key='{source_key}'"))
                })?;
                fake_source.insert(source_key.clone(), indicator_df.clone());
            }

            // 中文注释：ResultPack 公开 indicators 自带 time 列，这里只把它们当成“带 time 的 source”
            // 做同轴切片，再回收到 indicator 子集；不能再假装它覆盖了全部 source。
            let fake_pack = build_data_pack(
                fake_source,
                result.base_data_key.clone(),
                result.ranges.clone(),
                None,
            )?;
            let sliced_indicator_pack = slice_data_pack_by_base_window(&fake_pack, &result_indices)?;
            let mut out = HashMap::with_capacity(indicator_keys.len());
            for source_key in &indicator_keys {
                out.insert(
                    source_key.clone(),
                    sliced_indicator_pack.source[source_key].clone(),
                );
            }
            Some(out)
        }
        None => None,
        Some(_) => None,
    };

    let signals = match &result.signals {
        Some(df) => {
            validate_slice_bounds(df.height(), start, len, "signals")?;
            Some(df.slice(start as i64, len))
        }
        None => None,
    };
    let backtest = match &result.backtest {
        Some(df) => {
            validate_slice_bounds(df.height(), start, len, "backtest")?;
            Some(df.slice(start as i64, len))
        }
        None => None,
    };

    build_result_pack(
        &sliced_data_pack,
        indicators_with_time
            .as_ref()
            .map(strip_indicator_time_columns)
            .transpose()?,
        signals,
        backtest,
        None,
    )
}

fn build_result_slice_indices(
    indices: &WindowSliceIndices,
    base_data_key: &str,
    indicator_keys: &[String],
) -> Result<WindowSliceIndices, QuantError> {
    let mut source_ranges = HashMap::with_capacity(indicator_keys.len() + 1);
    let mut ranges_draft = HashMap::with_capacity(indicator_keys.len() + 1);
    source_ranges.insert(
        base_data_key.to_string(),
        indices
            .source_ranges
            .get(base_data_key)
            .ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "WindowSliceIndices.source_ranges 缺少 base_data_key='{}'",
                    base_data_key
                ))
            })?
            .clone(),
    );
    ranges_draft.insert(
        base_data_key.to_string(),
        indices
            .ranges_draft
            .get(base_data_key)
            .ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "WindowSliceIndices.ranges_draft 缺少 base_data_key='{}'",
                    base_data_key
                ))
            })?
            .clone(),
    );
    for source_key in indicator_keys {
        source_ranges.insert(
            source_key.clone(),
            indices
                .source_ranges
                .get(source_key)
                .ok_or_else(|| {
                    QuantError::InvalidParam(format!(
                        "WindowSliceIndices.source_ranges 缺少 indicators key='{source_key}'"
                    ))
                })?
                .clone(),
        );
        ranges_draft.insert(
            source_key.clone(),
            indices
                .ranges_draft
                .get(source_key)
                .ok_or_else(|| {
                    QuantError::InvalidParam(format!(
                        "WindowSliceIndices.ranges_draft 缺少 indicators key='{source_key}'"
                    ))
                })?
                .clone(),
        );
    }
    Ok(WindowSliceIndices {
        source_ranges,
        ranges_draft,
    })
}

pub fn derive_slice_indices_from_data_pack(
    data: &DataPack,
    start: usize,
    len: usize,
) -> Result<WindowSliceIndices, QuantError> {
    let mapping_height = data.mapping.height();
    if len == 0 {
        return Err(QuantError::InvalidParam(
            "窗口长度 len 必须 > 0".to_string(),
        ));
    }
    if start >= mapping_height || start + len > mapping_height {
        return Err(QuantError::InvalidParam(format!(
            "窗口切片越界: mapping_len={}, start={}, len={}",
            mapping_height, start, len
        )));
    }

    let base_warmup = data
        .ranges
        .get(&data.base_data_key)
        .map(|range| range.warmup_bars)
        .unwrap_or(0);
    let active_start = start.saturating_add(base_warmup.min(len.saturating_sub(1)));
    let active_range = (active_start, start + len);
    let required = data
        .ranges
        .iter()
        .map(|(source_key, range)| (source_key.clone(), range.warmup_bars))
        .collect::<HashMap<_, _>>();
    build_window_slice_indices(data, (start, start + len), active_range, &required)
        .map_err(Into::into)
}
