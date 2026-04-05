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

/// 中文注释：非 base source stitched 后允许同一大周期时间重复，但不允许时间倒退。
pub fn assert_source_times_non_decreasing(data: &DataPack) -> Result<(), QuantError> {
    for (source_key, src_df) in &data.source {
        if source_key == &data.base_data_key {
            continue;
        }
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
            if let (Some(p), Some(c)) = (prev, curr) {
                if c < p {
                    return Err(OptimizerError::InvalidConfig(format!(
                        "stitched source '{}' time 非递减校验失败: idx={} {} < {}",
                        source_key, i, c, p
                    ))
                    .into());
                }
            }
        }
    }
    Ok(())
}
