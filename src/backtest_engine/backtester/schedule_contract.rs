use crate::error::{BacktestError, QuantError};
use crate::types::BacktestParams;
use polars::prelude::Series;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 中文注释：分段回测的正式 schedule 输入对象，统一使用 stitched 绝对行轴的半开区间。
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct BacktestParamSegment {
    pub start_row: usize,
    pub end_row: usize,
    pub params: BacktestParams,
}

#[gen_stub_pymethods]
#[pymethods]
impl BacktestParamSegment {
    #[new]
    pub fn new(start_row: usize, end_row: usize, params: BacktestParams) -> Self {
        Self {
            start_row,
            end_row,
            params,
        }
    }
}

/// 中文注释：校验 schedule 必须从 0 开始、连续覆盖且正好覆盖到 data_length。
pub fn validate_schedule_contiguity(
    schedule: &[BacktestParamSegment],
    data_length: usize,
) -> Result<(), QuantError> {
    if schedule.is_empty() {
        return Err(BacktestError::ValidationError("schedule 不能为空".into()).into());
    }

    let first = &schedule[0];
    if first.start_row != 0 {
        return Err(BacktestError::ValidationError(format!(
            "schedule 首段必须从 0 开始，当前={}",
            first.start_row
        ))
        .into());
    }

    for (idx, segment) in schedule.iter().enumerate() {
        if segment.start_row >= segment.end_row {
            return Err(BacktestError::ValidationError(format!(
                "schedule 段必须满足 start_row < end_row，idx={idx}, start={}, end={}",
                segment.start_row, segment.end_row
            ))
            .into());
        }

        if idx + 1 < schedule.len() {
            let next = &schedule[idx + 1];
            if next.start_row != segment.end_row {
                return Err(BacktestError::ValidationError(format!(
                    "schedule 必须连续覆盖且不能 gap/overlap，idx={idx}, current_end={}, next_start={}",
                    segment.end_row, next.start_row
                ))
                .into());
            }
        }
    }

    let last = schedule.last().expect("非空 schedule 已校验");
    if last.end_row != data_length {
        return Err(BacktestError::ValidationError(format!(
            "schedule 末段必须覆盖到 data_length，current_end={}, data_length={data_length}",
            last.end_row
        ))
        .into());
    }

    Ok(())
}

/// 中文注释：ATR 契约只校验 Some/None 形态与长度，不在这里反向重算 ATR。
pub fn validate_schedule_atr_contract(
    schedule: &[BacktestParamSegment],
    atr_by_row: Option<&Series>,
    data_length: usize,
) -> Result<bool, QuantError> {
    let mut has_any_schedule_atr_param = false;
    for segment in schedule {
        let has_segment_atr = segment.params.validate_atr_consistency()?;
        has_any_schedule_atr_param |= has_segment_atr;
    }

    match (has_any_schedule_atr_param, atr_by_row) {
        (true, None) => Err(BacktestError::ValidationError(
            "schedule 启用了 ATR 相关参数，但 atr_by_row 缺失".into(),
        )
        .into()),
        (false, Some(_)) => Err(BacktestError::ValidationError(
            "schedule 未启用 ATR 相关参数，但 atr_by_row 不应传入".into(),
        )
        .into()),
        (_, Some(series)) if series.len() != data_length => {
            Err(BacktestError::ValidationError(format!(
                "atr_by_row 长度必须严格等于 data_length，actual={}, expected={data_length}",
                series.len()
            ))
            .into())
        }
        _ => Ok(has_any_schedule_atr_param),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params() -> BacktestParams {
        BacktestParams::default()
    }

    #[test]
    fn test_validate_schedule_contiguity_contract() {
        let schedule = vec![
            BacktestParamSegment::new(0, 3, params()),
            BacktestParamSegment::new(3, 5, params()),
        ];
        validate_schedule_contiguity(&schedule, 5).expect("连续 schedule 应通过");

        let bad = vec![
            BacktestParamSegment::new(0, 3, params()),
            BacktestParamSegment::new(4, 5, params()),
        ];
        assert!(validate_schedule_contiguity(&bad, 5).is_err());
    }
}
