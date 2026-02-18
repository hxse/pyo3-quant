use crate::error::QuantError;
use crate::types::DataContainer;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

fn extract_time_values(df: &DataFrame, source_key: &str) -> Result<Vec<i64>, QuantError> {
    let time_col = df
        .column("time")
        .map_err(|_| QuantError::InvalidParam(format!("source '{source_key}' 缺少 time 列")))?;
    let time_i64 = time_col.i64().map_err(|_| {
        QuantError::InvalidParam(format!("source '{source_key}' 的 time 列必须是 Int64"))
    })?;

    let mut out = Vec::with_capacity(time_i64.len());
    for v in time_i64.into_iter() {
        let ts = v.ok_or_else(|| {
            QuantError::InvalidParam(format!("source '{source_key}' 的 time 列存在 null"))
        })?;
        out.push(ts);
    }
    Ok(out)
}

fn build_backward_mapping(base_times: &[i64], src_times: &[i64]) -> Vec<Option<u32>> {
    let mut out = Vec::with_capacity(base_times.len());
    if src_times.is_empty() {
        out.resize(base_times.len(), None);
        return out;
    }

    let mut j: usize = 0;
    for &t in base_times {
        while j + 1 < src_times.len() && src_times[j + 1] <= t {
            j += 1;
        }
        if src_times[j] <= t {
            out.push(Some(j as u32));
        } else {
            out.push(None);
        }
    }
    out
}

fn align_sources_to_base_time_range(
    source: &mut HashMap<String, DataFrame>,
    base_key: &str,
) -> Result<(), QuantError> {
    let base_df = source
        .get(base_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    let base_times = extract_time_values(base_df, base_key)?;
    // 中文注释：base 为空时直接返回；后续 mapping 会按空 base 语义自然得到空映射。
    if base_times.is_empty() {
        return Ok(());
    }
    let base_start = *base_times.first().expect("checked non-empty");
    let base_end = *base_times.last().expect("checked non-empty");

    let source_keys: Vec<String> = source
        .keys()
        .filter(|k| k.as_str() != base_key)
        .cloned()
        .collect();

    for key in source_keys {
        let src_df = source
            .get(&key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{key}' 不存在")))?;
        let src_times = extract_time_values(src_df, &key)?;

        let predecessor_idx = src_times
            .iter()
            .enumerate()
            .filter(|(_, t)| **t < base_start)
            .map(|(i, _)| i)
            .last();

        // 中文注释：保留 base 时间范围内数据 + 范围前最后一根（用于 backward asof 衔接）。
        let mut keep_mask = Vec::with_capacity(src_times.len());
        for (idx, t) in src_times.iter().enumerate() {
            let in_base_range = *t >= base_start && *t <= base_end;
            let is_predecessor = predecessor_idx.map(|i| i == idx).unwrap_or(false);
            keep_mask.push(in_base_range || is_predecessor);
        }

        let mask = BooleanChunked::from_slice("keep".into(), &keep_mask);
        let filtered = src_df.filter(&mask).map_err(QuantError::from)?;
        source.insert(key, filtered);
    }

    Ok(())
}

fn is_natural_sequence_u32(series: &UInt32Chunked) -> bool {
    if series.null_count() > 0 {
        return false;
    }
    for (i, v) in series.into_no_null_iter().enumerate() {
        if v != i as u32 {
            return false;
        }
    }
    true
}

pub fn is_natural_mapping_for_source(
    data: &DataContainer,
    source_key: &str,
) -> Result<bool, QuantError> {
    let mapping_col = data.mapping.column(source_key).map_err(|_| {
        QuantError::InvalidParam(format!("mapping 中缺少 source 列 '{source_key}'"))
    })?;
    let mapping_u32 = mapping_col.u32().map_err(|_| {
        QuantError::InvalidParam(format!("mapping 列 '{source_key}' 必须为 UInt32"))
    })?;
    Ok(is_natural_sequence_u32(mapping_u32))
}

/// 基于 base 窗口切片 DataContainer，并重建窗口内局部 mapping。
///
/// 规则：
/// 1. 先按 base 窗口切 mapping；
/// 2. 每个 source 按窗口映射反推最小覆盖切片；
/// 3. 返回窗口内重基（local index）的 mapping；
/// 4. 不做就地修改，始终返回新 DataContainer。
pub fn slice_data_container_by_base_window(
    data: &DataContainer,
    start: usize,
    len: usize,
) -> Result<DataContainer, QuantError> {
    let mapping_height = data.mapping.height();
    if len == 0 {
        return Err(QuantError::InvalidParam(
            "窗口长度 len 必须 > 0".to_string(),
        ));
    }
    if start >= mapping_height || start + len > mapping_height {
        return Err(QuantError::InvalidParam(format!(
            "窗口切片越界: mapping_len={}, start={}, len={}",
            mapping_height, start, len
        )));
    }

    let mapping_window = data.mapping.slice(start as i64, len);
    let mapping_window_height = mapping_window.height();

    // 中文注释：窗口切片必须基于 mapping 反推每个 source 的最小覆盖区间，
    // 并把窗口内 mapping 重基到 local index，避免多周期窗口越界。
    let mut source_keys: Vec<String> = data.source.keys().cloned().collect();
    source_keys.sort_unstable();
    let source_count = source_keys.len();
    let mut sliced_source: std::collections::HashMap<String, DataFrame> =
        std::collections::HashMap::with_capacity(source_count);
    let mut rebased_mapping_cols: Vec<Column> = Vec::with_capacity(source_count);

    for source_key in source_keys {
        let source_df = data
            .source
            .get(&source_key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{source_key}' 不存在")))?;
        let source_len = source_df.height();

        let mapping_col = mapping_window.column(&source_key).map_err(|_| {
            QuantError::InvalidParam(format!("窗口映射中缺少列 '{source_key}'，无法完成切片"))
        })?;

        let mapping_u32 = mapping_col.u32().map_err(|_| {
            QuantError::InvalidParam(format!("映射列 '{source_key}' 必须是 UInt32"))
        })?;

        let should_skip_mapping = is_natural_mapping_for_source(data, &source_key)?;
        let (src_start, src_len) = if should_skip_mapping {
            if source_len < start + len {
                return Err(QuantError::InvalidParam(format!(
                    "Source '{source_key}' 长度不足 direct slice: source_len={}, start={}, len={}",
                    source_len, start, len
                )));
            }
            (start, len)
        } else {
            let mut min_idx: Option<usize> = None;
            let mut max_idx: Option<usize> = None;

            for idx in mapping_u32.into_iter().flatten() {
                let i = idx as usize;
                min_idx = Some(min_idx.map_or(i, |v| v.min(i)));
                max_idx = Some(max_idx.map_or(i, |v| v.max(i)));
            }

            match (min_idx, max_idx) {
                (Some(min_i), Some(max_i)) => {
                    if max_i >= source_len {
                        return Err(QuantError::InvalidParam(format!(
                            "映射越界: source='{source_key}', max_idx={}, source_len={}",
                            max_i, source_len
                        )));
                    }
                    (min_i, max_i - min_i + 1)
                }
                _ => (0, 0),
            }
        };

        let source_slice = source_df.slice(src_start as i64, src_len);
        sliced_source.insert(source_key.clone(), source_slice);

        let rebased_mapping_series = if src_len == 0 {
            let nulls: Vec<Option<u32>> = vec![None; mapping_window_height];
            Series::new(source_key.clone().into(), nulls)
        } else {
            let rebased: Vec<Option<u32>> = mapping_u32
                .into_iter()
                .map(|v| v.map(|x| x - src_start as u32))
                .collect();
            Series::new(source_key.clone().into(), rebased)
        };
        rebased_mapping_cols.push(rebased_mapping_series.into_column());
    }

    let rebased_mapping = DataFrame::new(rebased_mapping_cols).map_err(QuantError::from)?;
    let sliced_skip_mask = data
        .skip_mask
        .as_ref()
        .map(|df| df.slice(start as i64, len));

    Ok(DataContainer {
        source: sliced_source,
        mapping: rebased_mapping,
        skip_mask: sliced_skip_mask,
        base_data_key: data.base_data_key.clone(),
    })
}

/// 统一在 Rust 端构建时间映射（行号索引）。
///
/// 规则：
/// 1. 始终为每个 source 构建 mapping 列（含 base 列）；
/// 2. base 列映射为 0..n-1；
/// 3. 非 base 列采用 backward asof 语义。
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def build_time_mapping(
    data_dict: pyo3_quant.DataContainer,
    align_to_base_range: bool = True,
) -> pyo3_quant.DataContainer:
    """在 Rust 端构建 DataContainer.mapping（可选按 base 时间范围对齐）"""
"#
)]
#[pyfunction(name = "build_time_mapping")]
#[pyo3(signature = (data_dict, align_to_base_range=true))]
pub fn py_build_time_mapping(
    mut data_dict: DataContainer,
    align_to_base_range: bool,
) -> PyResult<DataContainer> {
    if align_to_base_range {
        align_sources_to_base_time_range(&mut data_dict.source, &data_dict.base_data_key)?;
    }

    let base_key = &data_dict.base_data_key;
    let base_df = data_dict
        .source
        .get(base_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    let base_times = extract_time_values(base_df, base_key)?;
    let base_len = base_times.len();

    let source_count = data_dict.source.len();
    let mut mapping_columns: Vec<Column> = Vec::with_capacity(source_count);

    let mut source_keys: Vec<String> = data_dict.source.keys().cloned().collect();
    source_keys.sort_unstable();

    for key in source_keys {
        if key == *base_key {
            let vals: Vec<u32> = (0..base_len as u32).collect();
            let series = Series::new(key.clone().into(), vals);
            mapping_columns.push(series.into_column());
            continue;
        }

        let src_df = data_dict
            .source
            .get(&key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{key}' 不存在")))?;
        let src_times = extract_time_values(src_df, &key)?;
        let mapped = build_backward_mapping(&base_times, &src_times);
        let series = Series::new(key.clone().into(), mapped);
        mapping_columns.push(series.into_column());
    }

    let mapping = DataFrame::new(mapping_columns).map_err(QuantError::from)?;

    Ok(DataContainer {
        source: data_dict.source,
        mapping,
        skip_mask: data_dict.skip_mask,
        base_data_key: data_dict.base_data_key,
    })
}

/// 在 Rust 端执行窗口切片，返回窗口 DataContainer。
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def slice_data_container(
    data_dict: pyo3_quant.DataContainer,
    start: int,
    length: int,
) -> pyo3_quant.DataContainer:
    """按 base 窗口切 DataContainer，并重基窗口内 mapping"""
"#
)]
#[pyfunction(name = "slice_data_container")]
pub fn py_slice_data_container(
    data_dict: DataContainer,
    start: usize,
    length: usize,
) -> PyResult<DataContainer> {
    slice_data_container_by_base_window(&data_dict, start, length).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def is_natural_mapping_column(
    data_dict: pyo3_quant.DataContainer,
    source_key: str,
) -> bool:
    """判断 mapping[source_key] 是否为 0..n-1 自然序列（fast-path 判定）"""
"#
)]
#[pyfunction(name = "is_natural_mapping_column")]
pub fn py_is_natural_mapping_column(
    data_dict: DataContainer,
    source_key: String,
) -> PyResult<bool> {
    is_natural_mapping_for_source(&data_dict, &source_key).map_err(Into::into)
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_build_time_mapping, m)?)?;
    m.add_function(wrap_pyfunction!(py_slice_data_container, m)?)?;
    m.add_function(wrap_pyfunction!(py_is_natural_mapping_column, m)?)?;
    Ok(())
}
