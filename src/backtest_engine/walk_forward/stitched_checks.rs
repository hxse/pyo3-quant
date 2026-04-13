use crate::error::{OptimizerError, QuantError};
use crate::types::DataPack;

pub fn assert_time_strictly_increasing(times: &[i64]) -> Result<(), QuantError> {
    if times.is_empty() {
        return Err(OptimizerError::InvalidConfig("stitched time is empty".into()).into());
    }
    for i in 1..times.len() {
        if times[i] <= times[i - 1] {
            return Err(OptimizerError::InvalidConfig(format!(
                "stitched time must be strictly increasing: idx={} {} <= {}",
                i,
                times[i],
                times[i - 1]
            ))
            .into());
        }
    }
    Ok(())
}

/// 中文注释：stitched 后所有 source 都必须满足正式严格递增契约。
pub fn assert_source_times_strictly_increasing(data: &DataPack) -> Result<(), QuantError> {
    for (source_key, src_df) in &data.source {
        let time_col = src_df.column("time").map_err(|_| {
            OptimizerError::InvalidConfig(format!("stitched source '{}' 缺少 time 列", source_key))
        })?;
        let time_i64 = time_col.i64().map_err(|_| {
            OptimizerError::InvalidConfig(format!(
                "stitched source '{}' 的 time 列必须是 Int64",
                source_key
            ))
        })?;
        for i in 1..time_i64.len() {
            let prev = time_i64.get(i - 1);
            let curr = time_i64.get(i);
            match (prev, curr) {
                (Some(p), Some(c)) if c > p => {}
                (Some(p), Some(c)) => {
                    return Err(OptimizerError::InvalidConfig(format!(
                        "stitched source '{}' time 必须严格递增: idx={}, prev={}, curr={}",
                        source_key, i, p, c
                    ))
                    .into());
                }
                _ => {
                    return Err(OptimizerError::InvalidConfig(format!(
                        "stitched source '{}' 的 time 列不允许包含空值: idx={}",
                        source_key, i
                    ))
                    .into());
                }
            }
        }
    }
    Ok(())
}
