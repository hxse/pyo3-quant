pub mod active_extract;
pub mod capital_rebuild;
pub mod data_pack_builder;
pub mod fetch_planner;
pub mod result_pack_builder;
pub mod slicing;
pub mod source_contract;
pub mod time_projection;
pub mod warmup_requirements;

use crate::types::{DataPack, ResultPack};
use polars::prelude::DataFrame;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

pub use self::active_extract::extract_active;
pub use self::capital_rebuild::{
    rebuild_capital_columns_for_stitched_backtest,
    rebuild_capital_columns_for_stitched_backtest_with_boundaries,
};
pub use self::data_pack_builder::build_data_pack;
pub use self::fetch_planner::{DataPackFetchPlanner, DataPackFetchPlannerInput, FetchRequest};
pub use self::result_pack_builder::{build_result_pack, strip_indicator_time_columns};
pub use self::slicing::{
    derive_slice_indices_from_data_pack, is_natural_mapping_for_source,
    slice_data_pack_by_base_window, slice_result_pack_by_base_window,
};
pub use self::source_contract::{
    build_full_data_pack, validate_base_data_key_is_smallest_interval,
};
pub(crate) use self::time_projection::extract_time_values;
pub use self::time_projection::{
    build_mapping_frame, exact_index_by_time, map_source_end_by_base_end, map_source_row_by_time,
    resolve_source_interval_ms, validate_coverage,
};
pub use self::warmup_requirements::{
    apply_wf_warmup_policy, build_warmup_requirements, merge_required_warmup_by_key,
    normalize_contract_warmup_by_key, resolve_backtest_exec_warmup_base,
    resolve_contract_warmup_by_key, WarmupRequirements,
};

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def build_time_mapping(
    source: dict[str, object],
    base_data_key: str,
    skip_mask = None,
    align_to_base_range: bool = False,
) -> pyo3_quant.DataPack:
    """从原始 source 直接构建带统一 mapping 的正式 DataPack"""
"#
)]
#[pyfunction(name = "build_time_mapping")]
#[pyo3(signature = (source, base_data_key, skip_mask=None, align_to_base_range=false))]
pub fn py_build_time_mapping(
    source: HashMap<String, Bound<'_, PyAny>>,
    base_data_key: String,
    skip_mask: Option<Bound<'_, PyAny>>,
    align_to_base_range: bool,
) -> PyResult<DataPack> {
    let mut source_inner = HashMap::new();
    for (key, value) in source {
        let df: pyo3_polars::PyDataFrame = value.extract()?;
        source_inner.insert(key, df.into());
    }
    let skip_mask_inner = match skip_mask {
        Some(value) => {
            let df: pyo3_polars::PyDataFrame = value.extract()?;
            Some(df.into())
        }
        None => None,
    };
    build_full_data_pack(
        source_inner,
        base_data_key,
        skip_mask_inner,
        align_to_base_range,
    )
    .map_err(Into::into)
}

/// 统一在 Rust 端构建时间映射（行号索引）。
///
/// 规则：
/// 1. 始终为每个 source 构建 mapping 列（含 base 列）；
/// 2. base 列映射为 0..n-1；
/// 3. 非 base 列采用前序 asof 语义。
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def slice_data_pack(
    data: pyo3_quant.DataPack,
    start: int,
    length: int,
) -> pyo3_quant.DataPack:
    """按 base 窗口切 DataPack，并重基窗口内 mapping"""
"#
)]
#[pyfunction(name = "slice_data_pack")]
pub fn py_slice_data_pack(data: DataPack, start: usize, length: usize) -> PyResult<DataPack> {
    let indices = derive_slice_indices_from_data_pack(&data, start, length)
        .map_err::<PyErr, _>(Into::into)?;
    slice_data_pack_by_base_window(&data, &indices).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def is_natural_mapping_column(
    data: pyo3_quant.DataPack,
    source_key: str,
) -> bool:
    """判断 mapping[source_key] 是否为 0..n-1 自然序列（fast-path 判定）"""
"#
)]
#[pyfunction(name = "is_natural_mapping_column")]
pub fn py_is_natural_mapping_column(data: DataPack, source_key: String) -> PyResult<bool> {
    is_natural_mapping_for_source(&data, &source_key).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def slice_result_pack(
    result: pyo3_quant.ResultPack,
    data: pyo3_quant.DataPack,
    start: int,
    length: int,
) -> pyo3_quant.ResultPack:
    """按 base 窗口切 ResultPack（含 indicators mapping 语义）"""
"#
)]
#[pyfunction(name = "slice_result_pack")]
pub fn py_slice_result_pack(
    result: ResultPack,
    data: DataPack,
    start: usize,
    length: usize,
) -> PyResult<ResultPack> {
    let indices = derive_slice_indices_from_data_pack(&data, start, length)
        .map_err::<PyErr, _>(Into::into)?;
    slice_result_pack_by_base_window(&result, &data, &indices).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def rebuild_stitched_capital_columns(
    backtest_df: object,
    initial_capital: float,
) -> object:
    """按 stitched 口径重建资金列（balance/equity/total_return_pct/fee_cum/current_drawdown）"""
"#
)]
#[pyfunction(name = "rebuild_stitched_capital_columns")]
pub fn py_rebuild_stitched_capital_columns(
    backtest_df: pyo3_polars::PyDataFrame,
    initial_capital: f64,
) -> PyResult<pyo3_polars::PyDataFrame> {
    let backtest_df_inner: DataFrame = backtest_df.into();
    let rebuilt =
        rebuild_capital_columns_for_stitched_backtest(&backtest_df_inner, initial_capital)?;
    Ok(pyo3_polars::PyDataFrame(rebuilt))
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    time_projection::register_py_module(m)?;
    data_pack_builder::register_py_module(m)?;
    result_pack_builder::register_py_module(m)?;
    active_extract::register_py_module(m)?;
    fetch_planner::register_py_module(m)?;
    m.add_function(wrap_pyfunction!(py_build_time_mapping, m)?)?;
    m.add_function(wrap_pyfunction!(py_slice_data_pack, m)?)?;
    m.add_function(wrap_pyfunction!(py_is_natural_mapping_column, m)?)?;
    m.add_function(wrap_pyfunction!(py_slice_result_pack, m)?)?;
    m.add_function(wrap_pyfunction!(py_rebuild_stitched_capital_columns, m)?)?;
    Ok(())
}
