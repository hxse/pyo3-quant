use crate::backtest_engine::data_ops::data_pack_builder::build_data_pack;
use crate::backtest_engine::data_ops::resolve_source_interval_ms;
use crate::backtest_engine::data_ops::time_projection::extract_time_values;
use crate::error::QuantError;
use crate::types::{DataPack, SourceRange};
use polars::prelude::*;
use std::collections::HashMap;

fn min_positive_interval_ms_from_times(
    times: &[i64],
    source_key: &str,
) -> Result<Option<i64>, QuantError> {
    if times.len() < 2 {
        return Ok(None);
    }

    let mut min_interval: Option<i64> = None;
    for pair in times.windows(2) {
        let diff = pair[1] - pair[0];
        if diff <= 0 {
            return Err(QuantError::InvalidParam(format!(
                "source '{source_key}' 的 time 列必须严格递增，检测到相邻间隔 {diff}"
            )));
        }
        min_interval = Some(match min_interval {
            Some(v) => v.min(diff),
            None => diff,
        });
    }

    Ok(min_interval)
}

/// 校验 base_data_key 对应的数据频率是否为全体 source 中最小周期（最细粒度）。
///
/// 规则：
/// 1. 全部 source key 都必须能通过 shared resolver 解析周期；
/// 2. 对全部 source，`time` 最小正间隔必须 >= 声明周期；
/// 3. `base_data_key` 必须命名规范并可解析周期；
/// 4. `base_data_key` 的声明周期必须是全部 source 中的最小周期。
fn validate_base_data_key_is_smallest_interval_for_source(
    source: &HashMap<String, DataFrame>,
    base_key: &str,
) -> Result<(), QuantError> {
    source
        .get(base_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    let base_declared_interval_ms = resolve_source_interval_ms(base_key)?;

    for (source_key, src_df) in source {
        let src_declared_interval_ms = resolve_source_interval_ms(source_key)?;
        let src_times = extract_time_values(src_df, source_key)?;
        let src_min_positive_interval_ms =
            min_positive_interval_ms_from_times(&src_times, source_key)?;

        // 中文注释：非 base source 在对齐裁剪后可能只剩一根 predecessor；
        // 这时无法再观测局部间隔，但仍允许继续走声明周期 + coverage 真值。
        if source_key == base_key && src_min_positive_interval_ms.is_none() {
            return Err(QuantError::InvalidParam(format!(
                "source '{source_key}' 的 time 列至少需要 2 行，当前为 {} 行",
                src_times.len()
            )));
        }

        // 中文注释：只做“过小”校验，允许最小间隔大于命名周期（例如节假日/停盘造成稀疏采样）。
        if let Some(observed_interval_ms) = src_min_positive_interval_ms {
            if observed_interval_ms < src_declared_interval_ms {
                return Err(QuantError::InvalidParam(format!(
                    "source '{source_key}' 的最小正间隔为 {observed_interval_ms}ms，小于命名周期 {src_declared_interval_ms}ms"
                )));
            }
        }

        if src_declared_interval_ms < base_declared_interval_ms {
            return Err(QuantError::InvalidParam(format!(
                "base_data_key 必须是最小周期：source '{source_key}' 的命名周期为 {src_declared_interval_ms}ms，小于 base '{base_key}' 的 {base_declared_interval_ms}ms"
            )));
        }
    }

    Ok(())
}

pub fn validate_base_data_key_is_smallest_interval(data: &DataPack) -> Result<(), QuantError> {
    validate_base_data_key_is_smallest_interval_for_source(&data.source, &data.base_data_key)
}

fn align_sources_to_base_time_range(
    source: &mut HashMap<String, DataFrame>,
    base_key: &str,
) -> Result<(), QuantError> {
    let base_df = source
        .get(base_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    let base_times = extract_time_values(base_df, base_key)?;
    // 中文注释：base 为空时直接返回；后续 mapping 会按空 base 语义自然得到空映射。
    if base_times.is_empty() {
        return Ok(());
    }
    let base_start = *base_times.first().expect("checked non-empty");
    let base_end = *base_times.last().expect("checked non-empty");

    let source_keys: Vec<String> = source
        .keys()
        .filter(|k| k.as_str() != base_key)
        .cloned()
        .collect();

    for key in source_keys {
        let src_df = source
            .get(&key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{key}' 不存在")))?;
        let src_times = extract_time_values(src_df, &key)?;

        let predecessor_idx = src_times
            .iter()
            .enumerate()
            .filter(|(_, t)| **t < base_start)
            .map(|(i, _)| i)
            .last();

        // 中文注释：保留 base 时间范围内数据 + 范围前最后一根（用于前序 asof 衔接）。
        let mut keep_mask = Vec::with_capacity(src_times.len());
        for (idx, t) in src_times.iter().enumerate() {
            let in_base_range = *t >= base_start && *t <= base_end;
            let is_predecessor = predecessor_idx.map(|i| i == idx).unwrap_or(false);
            keep_mask.push(in_base_range || is_predecessor);
        }

        let mask = BooleanChunked::from_slice("keep".into(), &keep_mask);
        let filtered = src_df.filter(&mask).map_err(QuantError::from)?;
        source.insert(key, filtered);
    }

    Ok(())
}

pub fn build_full_data_pack(
    mut source: HashMap<String, DataFrame>,
    base_data_key: String,
    skip_mask: Option<DataFrame>,
    align_to_base_range: bool,
) -> Result<DataPack, QuantError> {
    if align_to_base_range {
        align_sources_to_base_time_range(&mut source, &base_data_key)?;
    }
    let ranges = source
        .iter()
        .map(|(source_key, df)| {
            (
                source_key.clone(),
                SourceRange::new(0, df.height(), df.height()),
            )
        })
        .collect::<HashMap<_, _>>();
    build_data_pack(source, base_data_key, ranges, skip_mask)
}
