mod resolver;
mod types;

pub use resolver::{resolve_actions, ResolverParams};
// pub use types::{SignalAction, SignalState};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::PyErr;
use std::collections::HashMap;

use pyo3_stub_gen::derive::*;

#[gen_stub_pyfunction(module = "pyo3_quant.backtest_engine.action_resolver")]
#[pyfunction(name = "resolve_actions")]
/// Python绑定：解析 DataFrame 行为字典 (SignalState Dict)
pub fn py_resolve_actions(
    py: Python<'_>,
    row_dict: &Bound<'_, PyDict>,
    symbol: String,
    sl_exit_in_bar: bool,
    tp_exit_in_bar: bool,
) -> PyResult<Py<PyAny>> {
    // 仅提取解析器关心的数值列，避免把无关字段（如 bool）混入。
    // 这些列出现非数值类型时直接报错，防止静默吞掉脏数据。
    const REQUIRED_KEYS: [&str; 11] = [
        "frame_state",
        "entry_long_price",
        "entry_short_price",
        "sl_pct_price_long",
        "sl_pct_price_short",
        "sl_atr_price_long",
        "sl_atr_price_short",
        "tp_pct_price_long",
        "tp_pct_price_short",
        "tp_atr_price_long",
        "tp_atr_price_short",
    ];

    let mut row: HashMap<String, Option<f64>> = HashMap::new();
    for key in REQUIRED_KEYS {
        let maybe_value = row_dict.get_item(key)?;
        let value = match maybe_value {
            Some(value) => extract_optional_f64(key, value)?,
            None => None,
        };
        row.insert(key.to_string(), value);
    }

    let params = ResolverParams {
        symbol,
        sl_exit_in_bar,
        tp_exit_in_bar,
    };
    let state = resolve_actions(&row, &params);

    // Convert SignalState -> PyDict
    let dict = PyDict::new(py);
    let actions_list = PyList::empty(py);

    for action in state.actions {
        let action_dict = PyDict::new(py);
        action_dict.set_item("action_type", action.action_type)?;
        action_dict.set_item("symbol", action.symbol)?;
        action_dict.set_item("side", action.side)?;
        action_dict.set_item("price", action.price)?;
        actions_list.append(action_dict)?;
    }

    dict.set_item("actions", actions_list)?;
    dict.set_item("has_exit", state.has_exit)?;

    Ok(dict.into())
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_resolve_actions, m)?)?;
    Ok(())
}

fn extract_optional_f64(key: &str, value: Bound<'_, PyAny>) -> PyResult<Option<f64>> {
    if value.is_none() {
        return Ok(None);
    }
    value.extract::<f64>().map(Some).map_err(|e| {
        PyErr::new::<PyValueError, _>(format!("列 `{}` 需要为数值或 None: {}", key, e))
    })
}
