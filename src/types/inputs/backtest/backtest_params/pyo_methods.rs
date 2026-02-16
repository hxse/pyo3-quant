use crate::types::Param;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

use super::BacktestParams;

#[gen_stub_pymethods]
#[pymethods]
impl BacktestParams {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (
        *,
        sl_pct=None,
        tp_pct=None,
        tsl_pct=None,
        sl_atr=None,
        tp_atr=None,
        tsl_atr=None,
        atr_period=None,
        tsl_psar_af0=None,
        tsl_psar_af_step=None,
        tsl_psar_max_af=None,
        tsl_atr_tight=false,
        sl_exit_in_bar=false,
        tp_exit_in_bar=false,
        sl_trigger_mode=false,
        tp_trigger_mode=false,
        tsl_trigger_mode=false,
        sl_anchor_mode=false,
        tp_anchor_mode=false,
        tsl_anchor_mode=false,
        initial_capital=10000.0,
        fee_fixed=0.0,
        fee_pct=0.0006
    ))]
    pub fn new(
        sl_pct: Option<Param>,
        tp_pct: Option<Param>,
        tsl_pct: Option<Param>,
        sl_atr: Option<Param>,
        tp_atr: Option<Param>,
        tsl_atr: Option<Param>,
        atr_period: Option<Param>,
        tsl_psar_af0: Option<Param>,
        tsl_psar_af_step: Option<Param>,
        tsl_psar_max_af: Option<Param>,
        tsl_atr_tight: bool,
        sl_exit_in_bar: bool,
        tp_exit_in_bar: bool,
        sl_trigger_mode: bool,
        tp_trigger_mode: bool,
        tsl_trigger_mode: bool,
        sl_anchor_mode: bool,
        tp_anchor_mode: bool,
        tsl_anchor_mode: bool,
        initial_capital: f64,
        fee_fixed: f64,
        fee_pct: f64,
    ) -> Self {
        Self {
            initial_capital,
            fee_fixed,
            fee_pct,
            tsl_atr_tight,
            sl_exit_in_bar,
            tp_exit_in_bar,
            sl_trigger_mode,
            tp_trigger_mode,
            tsl_trigger_mode,
            sl_anchor_mode,
            tp_anchor_mode,
            tsl_anchor_mode,
            sl_pct,
            tp_pct,
            tsl_pct,
            sl_atr,
            tp_atr,
            tsl_atr,
            atr_period,
            tsl_psar_af0,
            tsl_psar_af_step,
            tsl_psar_max_af,
            ..Default::default()
        }
    }

    /// 业务层设置可优化参数（Option<Param> 字段）。
    /// 使用字段名精确更新，避免在 Python 侧做深层读改写回。
    pub fn set_optimizable_param(&mut self, name: &str, value: Option<Param>) -> PyResult<()> {
        match name {
            "sl_pct" => self.sl_pct = value,
            "tp_pct" => self.tp_pct = value,
            "tsl_pct" => self.tsl_pct = value,
            "sl_atr" => self.sl_atr = value,
            "tp_atr" => self.tp_atr = value,
            "tsl_atr" => self.tsl_atr = value,
            "atr_period" => self.atr_period = value,
            "tsl_psar_af0" => self.tsl_psar_af0 = value,
            "tsl_psar_af_step" => self.tsl_psar_af_step = value,
            "tsl_psar_max_af" => self.tsl_psar_max_af = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 可优化参数: {name}"
                )));
            }
        }
        Ok(())
    }

    /// 业务层设置布尔参数。
    pub fn set_bool_param(&mut self, name: &str, value: bool) -> PyResult<()> {
        match name {
            "tsl_atr_tight" => self.tsl_atr_tight = value,
            "sl_exit_in_bar" => self.sl_exit_in_bar = value,
            "tp_exit_in_bar" => self.tp_exit_in_bar = value,
            "sl_trigger_mode" => self.sl_trigger_mode = value,
            "tp_trigger_mode" => self.tp_trigger_mode = value,
            "tsl_trigger_mode" => self.tsl_trigger_mode = value,
            "sl_anchor_mode" => self.sl_anchor_mode = value,
            "tp_anchor_mode" => self.tp_anchor_mode = value,
            "tsl_anchor_mode" => self.tsl_anchor_mode = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 布尔参数: {name}"
                )));
            }
        }
        Ok(())
    }

    /// 业务层设置数值参数。
    pub fn set_f64_param(&mut self, name: &str, value: f64) -> PyResult<()> {
        match name {
            "initial_capital" => self.initial_capital = value,
            "fee_fixed" => self.fee_fixed = value,
            "fee_pct" => self.fee_pct = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 数值参数: {name}"
                )));
            }
        }
        Ok(())
    }
}
