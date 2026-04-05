use crate::error::{OptimizerError, QuantError};
use crate::types::DataPack;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackTimeRanges {
    pub warmup_time_range: Option<(i64, i64)>,
    pub active_time_range: (i64, i64),
    pub pack_time_range: (i64, i64),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WindowTimeRanges {
    pub train_warmup_time_range: Option<(i64, i64)>,
    pub train_active_time_range: (i64, i64),
    pub train_pack_time_range: (i64, i64),
    pub test_warmup_time_range: (i64, i64),
    pub test_active_time_range: (i64, i64),
    pub test_pack_time_range: (i64, i64),
}

pub fn extract_base_times(data: &DataPack) -> Result<Vec<i64>, QuantError> {
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| OptimizerError::NoData)?;
    let time_col = base_df.column("time")?.i64()?;

    let mut out = Vec::with_capacity(time_col.len());
    for value in time_col.into_iter() {
        let ts = value.ok_or_else(|| {
            OptimizerError::InvalidConfig("base time column contains null".into())
        })?;
        out.push(ts);
    }
    Ok(out)
}

pub fn build_window_time_ranges(
    train_pack_data: &DataPack,
    test_pack_data: &DataPack,
) -> Result<WindowTimeRanges, QuantError> {
    let train_ranges = build_pack_time_ranges(train_pack_data)?;
    let test_ranges = build_pack_time_ranges(test_pack_data)?;
    let test_warmup_time_range = test_ranges.warmup_time_range.ok_or_else(|| {
        OptimizerError::InvalidConfig("test_pack_data 缺少必填 warmup_time_range".into())
    })?;

    Ok(WindowTimeRanges {
        train_warmup_time_range: train_ranges.warmup_time_range,
        train_active_time_range: train_ranges.active_time_range,
        train_pack_time_range: train_ranges.pack_time_range,
        test_warmup_time_range,
        test_active_time_range: test_ranges.active_time_range,
        test_pack_time_range: test_ranges.pack_time_range,
    })
}

pub fn build_pack_time_ranges(pack: &DataPack) -> Result<PackTimeRanges, QuantError> {
    let base_range = pack.ranges.get(&pack.base_data_key).ok_or_else(|| {
        OptimizerError::InvalidConfig(format!(
            "pack.ranges 缺少 base key='{}'",
            pack.base_data_key
        ))
    })?;
    if base_range.active_bars == 0 {
        return Err(OptimizerError::InvalidConfig("pack base active_bars 必须 >= 1".into()).into());
    }

    let time_col =
        pack.mapping.column("time")?.i64().map_err(|_| {
            OptimizerError::InvalidConfig("pack.mapping['time'] 必须是 Int64".into())
        })?;
    if time_col.len() != base_range.pack_bars {
        return Err(OptimizerError::InvalidConfig(format!(
            "pack.mapping.height()={} 必须等于 base pack_bars={}",
            time_col.len(),
            base_range.pack_bars
        ))
        .into());
    }

    let times = time_col.into_no_null_iter().collect::<Vec<_>>();
    let pack_time_range = (
        *times
            .first()
            .ok_or_else(|| OptimizerError::InvalidConfig("pack time 为空".into()))?,
        *times
            .last()
            .ok_or_else(|| OptimizerError::InvalidConfig("pack time 为空".into()))?,
    );
    let warmup_time_range = if base_range.warmup_bars == 0 {
        None
    } else {
        Some((times[0], times[base_range.warmup_bars - 1]))
    };
    let active_start_idx = base_range.warmup_bars;
    let active_end_idx = base_range.pack_bars - 1;

    Ok(PackTimeRanges {
        warmup_time_range,
        active_time_range: (times[active_start_idx], times[active_end_idx]),
        pack_time_range,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{DataPack, SourceRange};
    use polars::prelude::{DataFrame, NamedFrom, Series};
    use std::collections::HashMap;

    fn dummy_pack(times: Vec<i64>, warmup_bars: usize) -> DataPack {
        let height = times.len();
        let source = HashMap::from([(
            "ohlcv_1m".to_string(),
            DataFrame::new(vec![Series::new("time".into(), times.clone()).into()])
                .expect("source 应成功"),
        )]);
        let mapping =
            DataFrame::new(vec![Series::new("time".into(), times).into()]).expect("mapping 应成功");
        DataPack::new_checked(
            source,
            mapping,
            None,
            "ohlcv_1m".to_string(),
            HashMap::from([(
                "ohlcv_1m".to_string(),
                SourceRange::new(warmup_bars, height - warmup_bars, height),
            )]),
        )
    }

    #[test]
    fn test_build_window_time_ranges_contract() {
        let train_pack = dummy_pack(vec![10, 20, 30], 0);
        let test_pack = dummy_pack(vec![40, 50, 60, 70, 80], 2);
        let ranges = build_window_time_ranges(&train_pack, &test_pack).expect("窗口时间范围应成功");

        assert_eq!(ranges.train_warmup_time_range, None);
        assert_eq!(ranges.train_active_time_range, (10, 30));
        assert_eq!(ranges.train_pack_time_range, (10, 30));
        assert_eq!(ranges.test_warmup_time_range, (40, 50));
        assert_eq!(ranges.test_active_time_range, (60, 80));
        assert_eq!(ranges.test_pack_time_range, (40, 80));
    }
}
