use crate::error::BacktestError;

use super::BacktestParams;

impl BacktestParams {
    /// 检查是否有任一ATR参数（sl_atr、tp_atr、tsl_atr）有效。
    pub fn has_any_atr_param(&self) -> bool {
        self.is_sl_atr_param_valid()
            || self.is_tp_atr_param_valid()
            || self.is_tsl_atr_param_valid()
    }

    /// 验证ATR参数的一致性。
    /// 当任一ATR参数有效时，atr_period必须存在且有效。
    /// 如果验证失败，返回错误信息。
    /// 返回 `has_any_atr_param` 的值，表示ATR参数整体是否有效。
    pub fn validate_atr_consistency(&self) -> Result<bool, BacktestError> {
        let has_any_atr_param = self.has_any_atr_param();

        // 只有当存在ATR参数时，才需要验证atr_period。
        if has_any_atr_param {
            let atr_period_valid = self
                .atr_period
                .as_ref()
                .is_some_and(|param| param.value > 0.0);

            if !atr_period_valid {
                return Err(BacktestError::InvalidParameter {
                    param_name: "atr_period".to_string(),
                    value: self
                        .atr_period
                        .as_ref()
                        .map(|param| param.value.to_string())
                        .unwrap_or_else(|| "None".to_string()),
                    reason: "当使用任何ATR相关参数时，atr_period必须存在且大于0".to_string(),
                });
            }
        }

        Ok(has_any_atr_param)
    }

    /// 验证所有参数的有效性。
    /// 返回 `Ok(())` 如果所有参数有效，否则返回详细的错误信息 `BacktestError::InvalidParameter`。
    /// 注意：基本参数验证已在 FromPyObject 实现中进行，此方法主要用于运行时验证。
    pub fn validate(&self) -> Result<(), BacktestError> {
        use crate::types::utils::{check_valid_f64, check_valid_param};

        // 0. 检查所有参数是否为 NaN 或无穷大。
        let f64_params = [
            ("initial_capital", self.initial_capital),
            ("fee_fixed", self.fee_fixed),
            ("fee_pct", self.fee_pct),
        ];
        for (name, value) in &f64_params {
            check_valid_f64(*value, name)?;
        }

        let param_params = [
            ("sl_pct", &self.sl_pct),
            ("tp_pct", &self.tp_pct),
            ("tsl_pct", &self.tsl_pct),
            ("sl_atr", &self.sl_atr),
            ("tp_atr", &self.tp_atr),
            ("tsl_atr", &self.tsl_atr),
            ("atr_period", &self.atr_period),
        ];
        for (name, param) in &param_params {
            check_valid_param(param, name)?;
        }

        // 1. 验证 initial_capital > 0。
        if self.initial_capital <= 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "initial_capital".to_string(),
                value: self.initial_capital.to_string(),
                reason: "初始本金必须大于0".to_string(),
            });
        }

        // 2. 验证手续费参数 >= 0。
        if self.fee_fixed < 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "fee_fixed".to_string(),
                value: self.fee_fixed.to_string(),
                reason: "固定手续费不能为负".to_string(),
            });
        }

        if self.fee_pct < 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "fee_pct".to_string(),
                value: self.fee_pct.to_string(),
                reason: "百分比手续费不能为负".to_string(),
            });
        }

        // 3. 验证触发模式和 exit_in_bar 的组合。
        if self.sl_exit_in_bar && !self.sl_trigger_mode {
            return Err(BacktestError::InvalidParameter {
                param_name: "sl_exit_in_bar".to_string(),
                value: "true".to_string(),
                reason: "sl_exit_in_bar 不能在 sl_trigger_mode 为 false (Close 模式) 时启用"
                    .to_string(),
            });
        }

        if self.tp_exit_in_bar && !self.tp_trigger_mode {
            return Err(BacktestError::InvalidParameter {
                param_name: "tp_exit_in_bar".to_string(),
                value: "true".to_string(),
                reason: "tp_exit_in_bar 不能在 tp_trigger_mode 为 false (Close 模式) 时启用"
                    .to_string(),
            });
        }

        Ok(())
    }
}
