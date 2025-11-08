use super::operand_resolver::{resolve_data_operand, resolve_right_operand, ResolvedOperand};
use crate::data_conversion::input::param_set::SignalParams;
use crate::data_conversion::input::template::{CompareOp, SignalCondition};
use crate::data_conversion::input::DataContainer;
use crate::data_conversion::output::IndicatorResults;
use crate::error::QuantError;
use polars::prelude::*;
use std::ops::{BitAnd, Not};

/// 执行比较操作的通用函数
fn perform_comparison(
    series: &Series,
    operand: &ResolvedOperand,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<BooleanChunked, QuantError> {
    match operand {
        ResolvedOperand::Series(ref b) => Ok(compare_series(series, b)?),
        ResolvedOperand::Scalar(value) => Ok(compare_scalar(series, *value)?),
    }
}

/// 评估单个 SignalCondition，返回一个布尔 Series
pub fn evaluate_condition(
    condition: &SignalCondition,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<Series, QuantError> {
    let series_a = resolve_data_operand(&condition.a, processed_data, indicator_dfs)?;
    let resolved_b =
        resolve_right_operand(&condition.b, processed_data, indicator_dfs, signal_params)?;

    let result = match condition.compare {
        CompareOp::GT => {
            perform_comparison(&series_a, &resolved_b, |a, b| a.gt(b), |a, v| a.gt(v))?
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::LT => {
            perform_comparison(&series_a, &resolved_b, |a, b| a.lt(b), |a, v| a.lt(v))?
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::GE => {
            perform_comparison(&series_a, &resolved_b, |a, b| a.gt_eq(b), |a, v| a.gt_eq(v))?
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::LE => {
            perform_comparison(&series_a, &resolved_b, |a, b| a.lt_eq(b), |a, v| a.lt_eq(v))?
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::EQ => {
            perform_comparison(&series_a, &resolved_b, |a, b| a.equal(b), |a, v| a.equal(v))?
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::NE => perform_comparison(
            &series_a,
            &resolved_b,
            |a, b| a.not_equal(b),
            |a, v| a.not_equal(v),
        )?
        .into_series()
        .fill_null(FillNullStrategy::Zero)?,
        CompareOp::CGT => {
            let current_gt =
                perform_comparison(&series_a, &resolved_b, |a, b| a.gt(b), |a, v| a.gt(v))?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_gt =
                perform_comparison(&previous_a, &previous_b, |a, b| a.gt(b), |a, v| a.gt(v))?;
            current_gt
                .bitand(previous_gt.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::CLT => {
            let current_lt =
                perform_comparison(&series_a, &resolved_b, |a, b| a.lt(b), |a, v| a.lt(v))?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_lt =
                perform_comparison(&previous_a, &previous_b, |a, b| a.lt(b), |a, v| a.lt(v))?;
            current_lt
                .bitand(previous_lt.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::CGE => {
            let current_ge =
                perform_comparison(&series_a, &resolved_b, |a, b| a.gt_eq(b), |a, v| a.gt_eq(v))?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_ge = perform_comparison(
                &previous_a,
                &previous_b,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?;
            current_ge
                .bitand(previous_ge.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::CLE => {
            let current_le =
                perform_comparison(&series_a, &resolved_b, |a, b| a.lt_eq(b), |a, v| a.lt_eq(v))?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_le = perform_comparison(
                &previous_a,
                &previous_b,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?;
            current_le
                .bitand(previous_le.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::CEQ => {
            let current_eq =
                perform_comparison(&series_a, &resolved_b, |a, b| a.equal(b), |a, v| a.equal(v))?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_eq = perform_comparison(
                &previous_a,
                &previous_b,
                |a, b| a.equal(b),
                |a, v| a.equal(v),
            )?;
            current_eq
                .bitand(previous_eq.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
        CompareOp::CNE => {
            let current_ne = perform_comparison(
                &series_a,
                &resolved_b,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?;
            let previous_a = series_a.shift(1);
            let previous_b = match resolved_b {
                ResolvedOperand::Series(series_b) => ResolvedOperand::Series(series_b.shift(1)),
                ResolvedOperand::Scalar(value) => ResolvedOperand::Scalar(value),
            };
            let previous_ne = perform_comparison(
                &previous_a,
                &previous_b,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?;
            current_ne
                .bitand(previous_ne.not())
                .into_series()
                .fill_null(FillNullStrategy::Zero)?
        }
    };

    Ok(result)
}
