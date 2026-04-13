use crate::error::QuantError;
use crate::types::{DataPack, ResultPack, SourceRange};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

use super::{build_data_pack, build_result_pack, strip_indicator_time_columns};

fn assert_same_series(left: &Column, right: &Column, context: &str) -> Result<(), QuantError> {
    if !left
        .as_materialized_series()
        .equals_missing(right.as_materialized_series())
    {
        return Err(QuantError::InvalidParam(format!("{context} 不一致")));
    }
    Ok(())
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
    }

    let new_data = build_data_pack(
        new_source,
        data.base_data_key.clone(),
        new_data_ranges,
        data.skip_mask
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
    )?;

    let indicators_with_time = match &result.indicators {
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
            }
            Some(out)
        }
        None => None,
    };

    let new_result = build_result_pack(
        &new_data,
        indicators_with_time
            .as_ref()
            .map(strip_indicator_time_columns)
            .transpose()?,
        result
            .signals
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
        result
            .backtest
            .as_ref()
            .map(|df| df.slice(base_cut as i64, base_range.active_bars)),
        result.performance.clone(),
    )?;

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
