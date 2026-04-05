use crate::error::QuantError;
use crate::types::{DataPack, ResultPack, SourceRange};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

fn assert_same_series(left: &Column, right: &Column, context: &str) -> Result<(), QuantError> {
    if !left
        .as_materialized_series()
        .equals_missing(right.as_materialized_series())
    {
        return Err(QuantError::InvalidParam(format!("{context} 不一致")));
    }
    Ok(())
}

fn slice_mapping_rebased(
    mapping: &DataFrame,
    base_cut: usize,
    retained_warmup_by_key: &HashMap<String, usize>,
) -> Result<DataFrame, QuantError> {
    let new_len = mapping.height().saturating_sub(base_cut);
    let mut columns = Vec::with_capacity(mapping.width());
    columns.push(mapping.column("time")?.slice(base_cut as i64, new_len));

    let mut source_keys: Vec<String> = retained_warmup_by_key.keys().cloned().collect();
    source_keys.sort_unstable();
    for source_key in source_keys {
        let warmup = retained_warmup_by_key[&source_key] as u32;
        let sliced = mapping.column(&source_key)?.slice(base_cut as i64, new_len);
        let values = sliced
            .u32()
            .map_err(|_| {
                QuantError::InvalidParam(format!("mapping['{source_key}'] 必须是 UInt32"))
            })?
            .into_no_null_iter()
            .map(|value| {
                value.checked_sub(warmup).ok_or_else(|| {
                    QuantError::InvalidParam(format!(
                        "mapping['{source_key}'] 在 active 重基时出现下溢"
                    ))
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        columns.push(Series::new(source_key.clone().into(), values).into_column());
    }

    Ok(DataFrame::new(columns)?)
}

pub fn extract_active(
    data: &DataPack,
    result: &ResultPack,
) -> Result<(DataPack, ResultPack), QuantError> {
    if data.base_data_key != result.base_data_key {
        return Err(QuantError::InvalidParam(
            "extract_active(...) 要求 DataPack / ResultPack 的 base_data_key 一致".to_string(),
        ));
    }
    assert_same_series(
        data.mapping.column("time")?,
        result.mapping.column("time")?,
        "result.mapping.time 与 data.mapping.time",
    )?;

    let base_key = &data.base_data_key;
    let base_range = data.ranges.get(base_key).ok_or_else(|| {
        QuantError::InvalidParam(format!("DataPack.ranges 缺少 base key '{base_key}'"))
    })?;
    let result_base_range = result.ranges.get(base_key).ok_or_else(|| {
        QuantError::InvalidParam(format!("ResultPack.ranges 缺少 base key '{base_key}'"))
    })?;
    if base_range != result_base_range {
        return Err(QuantError::InvalidParam(
            "extract_active(...) 输入前校验失败：base ranges 不一致".to_string(),
        ));
    }

    let base_cut = base_range.warmup_bars;
    let mut new_source = HashMap::new();
    let mut new_data_ranges = HashMap::new();
    let mut retained_warmup_by_key = HashMap::new();

    for (source_key, source_df) in &data.source {
        let range = data.ranges.get(source_key).ok_or_else(|| {
            QuantError::InvalidParam(format!("DataPack.ranges 缺少 key='{source_key}'"))
        })?;
        let new_df = source_df.slice(range.warmup_bars as i64, range.active_bars);
        new_source.insert(source_key.clone(), new_df);
        new_data_ranges.insert(
            source_key.clone(),
            SourceRange::new(0, range.active_bars, range.active_bars),
        );
        retained_warmup_by_key.insert(source_key.clone(), range.warmup_bars);
    }

    let new_data = DataPack::new_checked(
        new_source,
        slice_mapping_rebased(&data.mapping, base_cut, &retained_warmup_by_key)?,
        data.skip_mask
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
        data.base_data_key.clone(),
        new_data_ranges,
    );

    let indicator_keys = result
        .indicators
        .as_ref()
        .map(|map| map.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    let mut retained_indicator_warmup = HashMap::new();
    let mut new_result_ranges = HashMap::new();
    new_result_ranges.insert(
        base_key.clone(),
        SourceRange::new(0, base_range.active_bars, base_range.active_bars),
    );

    let new_indicators = match &result.indicators {
        Some(indicators) => {
            let mut out = HashMap::new();
            for (source_key, indicator_df) in indicators {
                let range = data.ranges.get(source_key).ok_or_else(|| {
                    QuantError::InvalidParam(format!("DataPack.ranges 缺少指标 key='{source_key}'"))
                })?;
                out.insert(
                    source_key.clone(),
                    indicator_df.slice(range.warmup_bars as i64, range.active_bars),
                );
                retained_indicator_warmup.insert(source_key.clone(), range.warmup_bars);
                new_result_ranges.insert(
                    source_key.clone(),
                    SourceRange::new(0, range.active_bars, range.active_bars),
                );
            }
            Some(out)
        }
        None => None,
    };

    let mut sorted_indicator_keys = indicator_keys;
    sorted_indicator_keys.sort_unstable();
    let mut result_mapping_columns = Vec::with_capacity(sorted_indicator_keys.len() + 1);
    result_mapping_columns.push(
        result
            .mapping
            .column("time")?
            .slice(base_cut as i64, base_range.active_bars),
    );
    for source_key in sorted_indicator_keys {
        let warmup = retained_indicator_warmup
            .get(&source_key)
            .copied()
            .ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "extract_active(...) 缺少指标 key='{source_key}' 的 warmup"
                ))
            })? as u32;
        let values = result
            .mapping
            .column(&source_key)?
            .slice(base_cut as i64, base_range.active_bars)
            .u32()
            .map_err(|_| {
                QuantError::InvalidParam(format!(
                    "ResultPack.mapping['{source_key}'] 必须是 UInt32"
                ))
            })?
            .into_no_null_iter()
            .map(|value| {
                value.checked_sub(warmup).ok_or_else(|| {
                    QuantError::InvalidParam(format!(
                        "ResultPack.mapping['{source_key}'] 在 active 重基时出现下溢"
                    ))
                })
            })
            .collect::<Result<Vec<_>, _>>()?;
        result_mapping_columns.push(Series::new(source_key.into(), values).into_column());
    }

    let new_result = ResultPack::new_checked(
        new_indicators,
        result
            .signals
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
        result
            .backtest
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
        result.performance.clone(),
        DataFrame::new(result_mapping_columns)?,
        new_result_ranges,
        result.base_data_key.clone(),
    );

    Ok((new_data, new_result))
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def extract_active(
    data: pyo3_quant.DataPack,
    result: pyo3_quant.ResultPack,
) -> tuple[pyo3_quant.DataPack, pyo3_quant.ResultPack]:
    """提取同源 DataPack / ResultPack 的 active 视图"""
"#
)]
#[pyfunction(name = "extract_active")]
pub fn py_extract_active(data: DataPack, result: ResultPack) -> PyResult<(DataPack, ResultPack)> {
    extract_active(&data, &result).map_err(Into::into)
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_extract_active, m)?)?;
    Ok(())
}
