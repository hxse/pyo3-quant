use crate::backtest_engine::data_ops::{extract_time_values, map_source_row_by_time};
use crate::error::QuantError;
use crate::types::{DataSource, SourceRange};
use std::collections::HashMap;

/// 中文注释：统一计算 planner.finish() 的初始 ranges，不在 builder 内重复推导。
pub fn build_initial_ranges(
    source: &DataSource,
    base_data_key: &str,
    required_warmup_by_key: &HashMap<String, usize>,
) -> Result<HashMap<String, SourceRange>, QuantError> {
    // 中文注释：finish() 阶段把“已经补齐的最终 source 数据”翻译成 SourceRange。
    // 真值锚点永远是 base 的 first_live_time，其他 source 都按这个时刻反投影。
    let base_df = source.get(base_data_key).ok_or_else(|| {
        QuantError::InvalidParam(format!("finish() 缺少 base source '{}'", base_data_key))
    })?;
    let base_times = extract_time_values(base_df, base_data_key)?;
    let base_required = required_warmup_by_key
        .get(base_data_key)
        .copied()
        .ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "required_warmup_by_key 缺少 base key '{}'",
                base_data_key
            ))
        })?;

    if base_times.len() < base_required + 1 {
        return Err(QuantError::InvalidParam(format!(
            "base '{}' 的最终 pack 长度 {} 不足以承载 warmup={} 与至少 1 根 live bar",
            base_data_key,
            base_times.len(),
            base_required
        )));
    }

    let base_first_live_time = base_times[base_required];
    let mut ranges = HashMap::new();
    ranges.insert(
        base_data_key.to_string(),
        SourceRange::new(
            base_required,
            base_times.len() - base_required,
            base_times.len(),
        ),
    );

    for (source_key, df) in source {
        if source_key == base_data_key {
            continue;
        }
        let source_times = extract_time_values(df, source_key)?;
        // 中文注释：mapped_src_idx 表示“base 首根 live bar 落在当前 source 的哪一行”。
        // 它天然就是当前 source 的 warmup_bars 值。
        let mapped_src_idx =
            map_source_row_by_time(base_first_live_time, &source_times, source_key)?;
        let required = required_warmup_by_key
            .get(source_key)
            .copied()
            .ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "required_warmup_by_key 缺少 source '{}'",
                    source_key
                ))
            })?;
        if mapped_src_idx < required {
            return Err(QuantError::InvalidParam(format!(
                "source '{}' 的最终 warmup={} 小于 required={}",
                source_key, mapped_src_idx, required
            )));
        }
        ranges.insert(
            source_key.clone(),
            SourceRange::new(
                mapped_src_idx,
                source_times.len() - mapped_src_idx,
                source_times.len(),
            ),
        );
    }

    Ok(ranges)
}
