mod backtest_params;
mod performance_metric;
mod performance_params;
mod single_param_set;

use crate::types::Param;
use std::collections::HashMap;

pub type IndicatorsParams = HashMap<String, HashMap<String, HashMap<String, Param>>>;
pub type SignalParams = HashMap<String, Param>;

pub use backtest_params::BacktestParams;
pub use performance_metric::PerformanceMetric;
pub use performance_params::PerformanceParams;
pub use single_param_set::{ParamContainer, SingleParamSet};
