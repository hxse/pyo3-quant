use crate::error::BacktestError;
use crate::types::Param;

/// 检查 f64 是否为 NaN 或无穷大
pub fn check_valid_f64(value: f64, param_name: &str) -> Result<(), BacktestError> {
    if !value.is_finite() {
        return Err(BacktestError::InvalidParameter {
            param_name: param_name.to_string(),
            value: value.to_string(),
            reason: "参数不能为 NaN 或无穷大".to_string(),
        });
    }
    Ok(())
}

/// 检查 Option<Param> 中的值是否为 NaN 或无穷大
pub fn check_valid_param(param_opt: &Option<Param>, param_name: &str) -> Result<(), BacktestError> {
    if let Some(param) = param_opt {
        if !param.value.is_finite() {
            return Err(BacktestError::InvalidParameter {
                param_name: param_name.to_string(),
                value: param.value.to_string(),
                reason: "参数不能为 NaN 或无穷大".to_string(),
            });
        }
    }
    Ok(())
}
