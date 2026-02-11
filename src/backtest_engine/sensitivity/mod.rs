//! 敏感性分析/参数抖动测试模块
//!
//! 在最优参数附近进行随机扰动，评估策略的稳健性。

pub mod runner;
pub mod types;

pub use self::runner::py_run_sensitivity_test;
#[allow(unused_imports)]
pub use self::runner::run_sensitivity_test;
#[allow(unused_imports)]
pub use self::types::{SensitivityConfig, SensitivityResult, SensitivitySample};
