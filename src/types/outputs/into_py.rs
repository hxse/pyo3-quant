use crate::types::inputs::{
    BacktestParams, Param, ParamType, PerformanceMetric, PerformanceParams, SingleParamSet,
};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

// ParamType
impl<'py> IntoPyObject<'py> for ParamType {
    type Target = pyo3::types::PyString;
    type Output = Bound<'py, pyo3::types::PyString>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let s = match self {
            ParamType::Float => "float",
            ParamType::Integer => "integer",
            ParamType::Boolean => "boolean",
        };
        Ok(pyo3::types::PyString::new(py, s))
    }
}

// Param
impl<'py> IntoPyObject<'py> for Param {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("value", self.value)?;
        dict.set_item("min", self.min)?;
        dict.set_item("max", self.max)?;
        dict.set_item("dtype", self.dtype)?;
        dict.set_item("optimize", self.optimize)?;
        dict.set_item("log_scale", self.log_scale)?;
        dict.set_item("step", self.step)?;
        Ok(dict)
    }
}

// BacktestParams
impl<'py> IntoPyObject<'py> for BacktestParams {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        // Helper macro to set optional param
        macro_rules! set_opt_param {
            ($field:ident) => {
                if let Some(p) = self.$field {
                    dict.set_item(stringify!($field), p)?;
                } else {
                    dict.set_item(stringify!($field), py.None())?;
                }
            };
        }

        set_opt_param!(sl_pct);
        set_opt_param!(tp_pct);
        set_opt_param!(tsl_pct);
        set_opt_param!(sl_atr);
        set_opt_param!(tp_atr);
        set_opt_param!(tsl_atr);
        set_opt_param!(atr_period);
        set_opt_param!(tsl_psar_af0);
        set_opt_param!(tsl_psar_af_step);
        set_opt_param!(tsl_psar_max_af);

        dict.set_item("tsl_atr_tight", self.tsl_atr_tight)?;
        dict.set_item("sl_exit_in_bar", self.sl_exit_in_bar)?;
        dict.set_item("tp_exit_in_bar", self.tp_exit_in_bar)?;
        dict.set_item("sl_trigger_mode", self.sl_trigger_mode)?;
        dict.set_item("tp_trigger_mode", self.tp_trigger_mode)?;
        dict.set_item("tsl_trigger_mode", self.tsl_trigger_mode)?;
        dict.set_item("sl_anchor_mode", self.sl_anchor_mode)?;
        dict.set_item("tp_anchor_mode", self.tp_anchor_mode)?;
        dict.set_item("tsl_anchor_mode", self.tsl_anchor_mode)?;
        dict.set_item("initial_capital", self.initial_capital)?;
        dict.set_item("fee_fixed", self.fee_fixed)?;
        dict.set_item("fee_pct", self.fee_pct)?;

        Ok(dict)
    }
}

// PerformanceMetric
impl<'py> IntoPyObject<'py> for PerformanceMetric {
    type Target = pyo3::types::PyString;
    type Output = Bound<'py, pyo3::types::PyString>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let s = match self {
            PerformanceMetric::SharpeRatio => "sharpe_ratio",
            PerformanceMetric::SortinoRatio => "sortino_ratio",
            PerformanceMetric::CalmarRatio => "calmar_ratio",
            PerformanceMetric::MaxDrawdown => "max_drawdown",
            PerformanceMetric::TotalReturn => "total_return",
            PerformanceMetric::AnnualizationFactor => "annualization_factor",
            PerformanceMetric::WinRate => "win_rate",
            PerformanceMetric::ProfitLossRatio => "profit_loss_ratio",
            PerformanceMetric::MaxDrawdownDuration => "max_drawdown_duration",
            PerformanceMetric::TotalTrades => "total_trades",
            PerformanceMetric::AvgDailyTrades => "avg_daily_trades",
            PerformanceMetric::AvgHoldingDuration => "avg_holding_duration",
            PerformanceMetric::AvgEmptyDuration => "avg_empty_duration",
            PerformanceMetric::MaxHoldingDuration => "max_holding_duration",
            PerformanceMetric::MaxEmptyDuration => "max_empty_duration",
            PerformanceMetric::MaxSafeLeverage => "max_safe_leverage",
            PerformanceMetric::HasLeadingNanCount => "has_leading_nan_count",
            PerformanceMetric::SharpeRatioRaw => "sharpe_ratio_raw",
            PerformanceMetric::SortinoRatioRaw => "sortino_ratio_raw",
            PerformanceMetric::CalmarRatioRaw => "calmar_ratio_raw",
        };
        Ok(pyo3::types::PyString::new(py, s))
    }
}

// PerformanceParams
impl<'py> IntoPyObject<'py> for PerformanceParams {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        let metrics_list = PyList::empty(py);
        for metric in self.metrics {
            metrics_list.append(metric)?;
        }
        dict.set_item("metrics", metrics_list)?;
        dict.set_item("risk_free_rate", self.risk_free_rate)?;
        if let Some(factor) = self.leverage_safety_factor {
            dict.set_item("leverage_safety_factor", factor)?;
        } else {
            dict.set_item("leverage_safety_factor", py.None())?;
        }
        Ok(dict)
    }
}

// SingleParamSet
impl<'py> IntoPyObject<'py> for SingleParamSet {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        // Indicators
        let indicators_dict = PyDict::new(py);
        for (tf, groups) in self.indicators {
            let groups_dict = PyDict::new(py);
            for (group, params) in groups {
                let params_dict = PyDict::new(py);
                for (name, param) in params {
                    params_dict.set_item(name, param)?;
                }
                groups_dict.set_item(group, params_dict)?;
            }
            indicators_dict.set_item(tf, groups_dict)?;
        }
        dict.set_item("indicators", indicators_dict)?;

        // Signal
        let signal_dict = PyDict::new(py);
        for (name, param) in self.signal {
            signal_dict.set_item(name, param)?;
        }
        dict.set_item("signal", signal_dict)?;

        // Backtest
        dict.set_item("backtest", self.backtest)?;

        // Performance
        dict.set_item("performance", self.performance)?;

        Ok(dict)
    }
}
