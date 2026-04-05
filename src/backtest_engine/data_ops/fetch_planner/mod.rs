//! 分阶段取数 planner。
//!
//! 中文注释：这个模块不直接负责拉数据本身，而是把“下一轮该向哪个 source 要多少数据”
//! 抽象成一个显式状态机，供 Python / 上层调用方按轮次喂响应。

pub mod initial_ranges;
pub mod planner;
pub mod source_state;

pub use self::planner::{DataPackFetchPlanner, DataPackFetchPlannerInput, FetchRequest};

use pyo3::prelude::*;

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 中文注释：这里只注册 planner 对外暴露的最小 Python 边界，内部状态类型不直接导出。
    m.add_class::<DataPackFetchPlannerInput>()?;
    m.add_class::<FetchRequest>()?;
    m.add_class::<DataPackFetchPlanner>()?;
    Ok(())
}
