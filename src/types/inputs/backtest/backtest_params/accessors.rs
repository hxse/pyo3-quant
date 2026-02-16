use crate::types::Param;

use super::BacktestParams;

impl BacktestParams {
    /// 检查sl_pct参数是否有效（不验证其他参数）。
    /// 当 `sl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_pct_param_valid(&self) -> bool {
        self.sl_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tp_pct参数是否有效（不验证其他参数）。
    /// 当 `tp_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_pct_param_valid(&self) -> bool {
        self.tp_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tsl_pct参数是否有效（不验证其他参数）。
    /// 当 `tsl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_pct_param_valid(&self) -> bool {
        self.tsl_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查sl_atr参数是否有效（不验证atr_period）。
    /// 当 `sl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_atr_param_valid(&self) -> bool {
        self.sl_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tp_atr参数是否有效（不验证atr_period）。
    /// 当 `tp_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_atr_param_valid(&self) -> bool {
        self.tp_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tsl_atr参数是否有效（不验证atr_period）。
    /// 当 `tsl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_atr_param_valid(&self) -> bool {
        self.tsl_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查 PSAR 止损参数是否有效。
    /// 三个参数必须全部存在且大于0，或全部不存在。
    pub fn is_tsl_psar_param_valid(&self) -> bool {
        self.tsl_psar_af0.as_ref().is_some_and(|p| p.value > 0.0)
            && self
                .tsl_psar_af_step
                .as_ref()
                .is_some_and(|p| p.value > 0.0)
            && self.tsl_psar_max_af.as_ref().is_some_and(|p| p.value > 0.0)
    }

    /// 获取可优化参数的不可变引用。
    pub fn get_optimizable_param(&self, name: &str) -> Option<&Param> {
        match name {
            "sl_pct" => self.sl_pct.as_ref(),
            "tp_pct" => self.tp_pct.as_ref(),
            "tsl_pct" => self.tsl_pct.as_ref(),
            "sl_atr" => self.sl_atr.as_ref(),
            "tp_atr" => self.tp_atr.as_ref(),
            "tsl_atr" => self.tsl_atr.as_ref(),
            "atr_period" => self.atr_period.as_ref(),
            "tsl_psar_af0" => self.tsl_psar_af0.as_ref(),
            "tsl_psar_af_step" => self.tsl_psar_af_step.as_ref(),
            "tsl_psar_max_af" => self.tsl_psar_max_af.as_ref(),
            _ => None,
        }
    }

    /// 获取可优化参数的可变引用。
    pub fn get_optimizable_param_mut(&mut self, name: &str) -> Option<&mut Param> {
        match name {
            "sl_pct" => self.sl_pct.as_mut(),
            "tp_pct" => self.tp_pct.as_mut(),
            "tsl_pct" => self.tsl_pct.as_mut(),
            "sl_atr" => self.sl_atr.as_mut(),
            "tp_atr" => self.tp_atr.as_mut(),
            "tsl_atr" => self.tsl_atr.as_mut(),
            "atr_period" => self.atr_period.as_mut(),
            "tsl_psar_af0" => self.tsl_psar_af0.as_mut(),
            "tsl_psar_af_step" => self.tsl_psar_af_step.as_mut(),
            "tsl_psar_max_af" => self.tsl_psar_max_af.as_mut(),
            _ => None,
        }
    }

    /// 获取所有可优化参数名称。
    pub const OPTIMIZABLE_PARAMS: &'static [&'static str] = &[
        "sl_pct",
        "tp_pct",
        "tsl_pct",
        "sl_atr",
        "tp_atr",
        "tsl_atr",
        "atr_period",
        "tsl_psar_af0",
        "tsl_psar_af_step",
        "tsl_psar_max_af",
    ];
}
