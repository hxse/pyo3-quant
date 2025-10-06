use polars::prelude::*;
use std::collections::HashMap;
use crate::data_conversion::input::PerformanceParams;
use crate::data_conversion::output::PerformanceMetrics;

pub fn analyze_performance(
    _backtest_result_df: &DataFrame,
    performance_params: &PerformanceParams,
) -> PolarsResult<HashMap<String, f64>> {

    let mut result = HashMap::new();

    for metric_name in &performance_params.metrics {
        let value = match metric_name.as_ref() {
            "total_return" => 0.0,
            "sharpe_ratio" => 0.0,
            "max_drawdown" => 0.0,
            _ => {
                eprintln!("Warning: Unknown metric '{}' skipped", metric_name);
                continue;
            }
        };

        result.insert(metric_name.clone(), value);
    }

    Ok(result)
}
