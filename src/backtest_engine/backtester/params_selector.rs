use crate::backtest_engine::backtester::schedule_contract::BacktestParamSegment;
use crate::error::{BacktestError, QuantError};
use crate::types::BacktestParams;

/// 中文注释：selector 只保留 schedule 借用与当前 segment 游标，不展开成逐行参数副本。
pub struct ParamsSelector<'a> {
    schedule: &'a [BacktestParamSegment],
    segment_idx: usize,
}

pub fn build_schedule_params_selector(schedule: &[BacktestParamSegment]) -> ParamsSelector<'_> {
    ParamsSelector {
        schedule,
        segment_idx: 0,
    }
}

/// 中文注释：row_idx 单调递增时，segment_idx 也只增不减，不允许越界沿用最后一段。
pub fn select_params_for_row<'a>(
    selector: &'a mut ParamsSelector<'_>,
    row_idx: usize,
) -> Result<&'a BacktestParams, QuantError> {
    while selector.segment_idx < selector.schedule.len()
        && row_idx >= selector.schedule[selector.segment_idx].end_row
    {
        selector.segment_idx += 1;
    }

    let segment = selector.schedule.get(selector.segment_idx).ok_or_else(|| {
        BacktestError::ValidationError(format!(
            "row_idx={row_idx} 找不到对应 segment，schedule_len={}",
            selector.schedule.len()
        ))
    })?;

    if row_idx < segment.start_row || row_idx >= segment.end_row {
        return Err(BacktestError::ValidationError(format!(
            "row_idx={row_idx} 不落在当前 segment 范围内，segment_idx={}, range=[{}, {})",
            selector.segment_idx, segment.start_row, segment.end_row
        ))
        .into());
    }

    Ok(&segment.params)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::BacktestParams;

    fn params(initial_capital: f64) -> BacktestParams {
        let mut params = BacktestParams::default();
        params.initial_capital = initial_capital;
        params
    }

    #[test]
    fn test_params_selector_contract() {
        let schedule = vec![
            BacktestParamSegment::new(0, 2, params(10_000.0)),
            BacktestParamSegment::new(2, 5, params(20_000.0)),
        ];
        let mut selector = build_schedule_params_selector(&schedule);

        assert_eq!(
            select_params_for_row(&mut selector, 0)
                .expect("row 0 应命中首段")
                .initial_capital,
            10_000.0
        );
        assert_eq!(
            select_params_for_row(&mut selector, 3)
                .expect("row 3 应命中第二段")
                .initial_capital,
            20_000.0
        );
        assert!(select_params_for_row(&mut selector, 5).is_err());
    }
}
