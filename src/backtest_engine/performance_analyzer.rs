use crate::data_conversion::input::param_set::{PerformanceMetric, PerformanceParams};
use crate::data_conversion::output::PerformanceMetrics;
use polars::prelude::*;
use std::collections::HashMap;

pub fn analyze_performance(
    backtest_df: &DataFrame,
    performance_params: &PerformanceParams,
) -> PolarsResult<HashMap<String, f64>> {
    let mut result = HashMap::new();

    for metric in &performance_params.metrics {
        let value = match metric {
            PerformanceMetric::TotalReturn => 0.0,
            PerformanceMetric::SharpeRatio => 0.0,
            PerformanceMetric::MaxDrawdown => 0.0,
        };

        result.insert(metric.as_str().to_string(), value);
    }

    Ok(result)
}
