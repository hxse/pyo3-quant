pub mod data_splitter;
pub mod runner;

use pyo3::prelude::*;

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(runner::py_run_walk_forward, m)?)?;
    // Config 和 Result 都是直接转换的，不需要作为类注册，
    // 除非我们需要在 Python 端构造 Config (DTO)。
    // WalkForwardConfig 有 #[derive(FromPyObject)]，Python传参会自动转换。
    // 但是为了方便 Python 端类型提示，我们可能不需要在 Rust 端注册类，
    // 只要 Python 端有对应的定义即可。
    Ok(())
}
