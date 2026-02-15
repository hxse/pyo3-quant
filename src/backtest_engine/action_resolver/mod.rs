mod resolver;
mod types;

pub use resolver::{resolve_actions, ResolverParams};
// pub use types::{SignalAction, SignalState};

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
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
    let mut row: HashMap<String, Option<f64>> = HashMap::new();
    for (key, value) in row_dict.iter() {
        let key_str: String = key.extract()?;
        let val: Option<f64> = if value.is_none() {
            None
        } else {
            value.extract().ok()
        };
        row.insert(key_str, val);
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
