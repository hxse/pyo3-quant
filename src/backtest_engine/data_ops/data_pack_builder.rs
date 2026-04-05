use crate::error::QuantError;
use crate::types::{DataPack, DataSource, SourceRange};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::{HashMap, HashSet};

use super::time_projection::build_mapping_frame;
use super::validate_base_data_key_is_smallest_interval;

fn validate_skip_mask(skip_mask: &Option<DataFrame>, base_height: usize) -> Result<(), QuantError> {
    let Some(df) = skip_mask else {
        return Ok(());
    };

    if df.width() != 1 {
        return Err(QuantError::InvalidParam(
            "skip_mask 必须是单列表 DataFrame".to_string(),
        ));
    }
    if df.get_column_names().first().map(|v| v.as_str()) != Some("skip") {
        return Err(QuantError::InvalidParam(
            "skip_mask 的唯一合法列名必须是 'skip'".to_string(),
        ));
    }
    let skip_col = df.column("skip").map_err(QuantError::from)?;
    let skip_bool = skip_col.bool().map_err(|_| {
        QuantError::InvalidParam("skip_mask['skip'] 的 dtype 必须是 Boolean".to_string())
    })?;
    if skip_bool.null_count() > 0 {
        return Err(QuantError::InvalidParam(
            "skip_mask['skip'] 不允许存在 null".to_string(),
        ));
    }
    if df.height() != base_height {
        return Err(QuantError::InvalidParam(format!(
            "skip_mask.height()={} 必须等于 base 高度 {}",
            df.height(),
            base_height
        )));
    }
    Ok(())
}

fn validate_ranges(
    source: &DataSource,
    ranges: &HashMap<String, SourceRange>,
) -> Result<(), QuantError> {
    let source_keys: HashSet<&String> = source.keys().collect();
    let range_keys: HashSet<&String> = ranges.keys().collect();
    if source_keys != range_keys {
        return Err(QuantError::InvalidParam(
            "ranges 必须完整且仅覆盖全部 source keys".to_string(),
        ));
    }

    for (source_key, df) in source {
        let range = ranges
            .get(source_key)
            .ok_or_else(|| QuantError::InvalidParam(format!("ranges 缺少 key='{source_key}'")))?;
        if range.warmup_bars > range.pack_bars {
            return Err(QuantError::InvalidParam(format!(
                "ranges['{source_key}'].warmup_bars 不能大于 pack_bars"
            )));
        }
        if range.active_bars > range.pack_bars {
            return Err(QuantError::InvalidParam(format!(
                "ranges['{source_key}'].active_bars 不能大于 pack_bars"
            )));
        }
        if range.warmup_bars + range.active_bars != range.pack_bars {
            return Err(QuantError::InvalidParam(format!(
                "ranges['{source_key}'] 必须满足 warmup_bars + active_bars == pack_bars"
            )));
        }
        if range.pack_bars != df.height() {
            return Err(QuantError::InvalidParam(format!(
                "ranges['{source_key}'].pack_bars={} 必须等于 source['{source_key}'].height()={}",
                range.pack_bars,
                df.height()
            )));
        }
    }

    Ok(())
}

pub fn build_data_pack(
    source: DataSource,
    base_data_key: String,
    ranges: HashMap<String, SourceRange>,
    skip_mask: Option<DataFrame>,
) -> Result<DataPack, QuantError> {
    let base_df = source.get(&base_data_key).ok_or_else(|| {
        QuantError::InvalidParam(format!("base_data_key '{base_data_key}' 不存在于 source"))
    })?;
    let precheck_pack = DataPack::new_checked(
        source.clone(),
        DataFrame::empty(),
        skip_mask.clone(),
        base_data_key.clone(),
        ranges.clone(),
    );
    validate_base_data_key_is_smallest_interval(&precheck_pack)?;
    validate_ranges(&source, &ranges)?;
    validate_skip_mask(&skip_mask, base_df.height())?;

    let mapping = build_mapping_frame(&source, &base_data_key)?;
    if mapping.height() != base_df.height() {
        return Err(QuantError::InvalidParam(format!(
            "mapping.height()={} 必须等于 source[base].height()={}",
            mapping.height(),
            base_df.height()
        )));
    }
    if let Some(df) = &skip_mask {
        if df.height() != mapping.height() {
            return Err(QuantError::InvalidParam(format!(
                "skip_mask.height()={} 必须等于 mapping.height()={}",
                df.height(),
                mapping.height()
            )));
        }
    }

    let pack = DataPack::new_checked(source, mapping, skip_mask, base_data_key, ranges);
    Ok(pack)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def build_data_pack(
    source: dict[str, object],
    base_data_key: str,
    ranges: dict[str, pyo3_quant.SourceRange],
    skip_mask = None,
) -> pyo3_quant.DataPack:
    """按统一 contract 构建 DataPack"""
"#
)]
#[pyfunction(name = "build_data_pack")]
#[pyo3(signature = (source, base_data_key, ranges, skip_mask=None))]
pub fn py_build_data_pack(
    py: Python<'_>,
    source: HashMap<String, Bound<'_, PyAny>>,
    base_data_key: String,
    ranges: HashMap<String, Py<SourceRange>>,
    skip_mask: Option<Bound<'_, PyAny>>,
) -> PyResult<DataPack> {
    let mut source_inner = HashMap::new();
    for (key, value) in source {
        let df: PyDataFrame = value.extract()?;
        source_inner.insert(key, df.into());
    }

    let mut range_inner = HashMap::new();
    for (key, value) in ranges {
        let bound = value.bind(py);
        let borrowed = bound.borrow();
        range_inner.insert(key, borrowed.clone());
    }

    let skip_mask_inner = match skip_mask {
        Some(value) => {
            let df: PyDataFrame = value.extract()?;
            Some(df.into())
        }
        None => None,
    };

    build_data_pack(source_inner, base_data_key, range_inner, skip_mask_inner).map_err(Into::into)
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_build_data_pack, m)?)?;
    Ok(())
}
