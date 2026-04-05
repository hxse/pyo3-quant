use crate::error::QuantError;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// 中文注释：抽取并校验 time 列，统一要求 Int64、无 null、严格递增。
pub(crate) fn extract_time_values(
    df: &DataFrame,
    source_key: &str,
) -> Result<Vec<i64>, QuantError> {
    let time_col = df
        .column("time")
        .map_err(|_| QuantError::InvalidParam(format!("source '{source_key}' 缺少 time 列")))?;
    let time_i64 = time_col.i64().map_err(|_| {
        QuantError::InvalidParam(format!("source '{source_key}' 的 time 列必须是 Int64"))
    })?;

    let mut out = Vec::with_capacity(time_i64.len());
    let mut prev: Option<i64> = None;
    for value in time_i64 {
        let current = value.ok_or_else(|| {
            QuantError::InvalidParam(format!("source '{source_key}' 的 time 列存在 null"))
        })?;
        if let Some(prev_value) = prev {
            if current <= prev_value {
                return Err(QuantError::InvalidParam(format!(
                    "source '{source_key}' 的 time 列必须严格递增，检测到 {} <= {}",
                    current, prev_value
                )));
            }
        }
        prev = Some(current);
        out.push(current);
    }
    Ok(out)
}

/// 中文注释：唯一声明周期解析入口，支持常见交易周期与工程约定单位。
pub fn resolve_source_interval_ms(source_key: &str) -> Result<i64, QuantError> {
    let (_, period_part) = source_key.rsplit_once('_').ok_or_else(|| {
        QuantError::InvalidParam(format!(
            "source_key '{source_key}' 非法，必须形如 'ohlcv_1m'"
        ))
    })?;

    let digit_len = period_part
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .count();
    if digit_len == 0 || digit_len == period_part.len() {
        return Err(QuantError::InvalidParam(format!(
            "source_key '{source_key}' 的周期后缀非法，必须包含正整数和单位"
        )));
    }

    let value = period_part[..digit_len].parse::<i64>().map_err(|_| {
        QuantError::InvalidParam(format!("source_key '{source_key}' 的周期值必须是正整数"))
    })?;
    if value <= 0 {
        return Err(QuantError::InvalidParam(format!(
            "source_key '{source_key}' 的周期值必须 > 0"
        )));
    }

    let raw_unit = &period_part[digit_len..];
    let unit_ms = match raw_unit {
        "ms" => 1_i64,
        "s" => 1_000_i64,
        "m" => 60_000_i64,
        "h" => 3_600_000_i64,
        "d" => 86_400_000_i64,
        "w" => 7_i64 * 86_400_000_i64,
        "M" => 28_i64 * 86_400_000_i64,
        "y" => 364_i64 * 86_400_000_i64,
        unit => {
            return Err(QuantError::InvalidParam(format!(
                "source_key '{source_key}' 的周期单位 '{unit}' 非法"
            )))
        }
    };

    value.checked_mul(unit_ms).ok_or_else(|| {
        QuantError::InvalidParam(format!("source_key '{source_key}' 的周期毫秒数发生溢出"))
    })
}

pub fn exact_index_by_time(
    times: &[i64],
    target_time: i64,
    column_name: &str,
) -> Result<usize, QuantError> {
    if times.is_empty() {
        return Err(QuantError::InvalidParam(format!(
            "列 '{column_name}' 为空，无法定位 time={target_time}"
        )));
    }

    times.binary_search(&target_time).map_err(|_| {
        QuantError::InvalidParam(format!(
            "列 '{column_name}' 中不存在唯一 time={target_time}"
        ))
    })
}

pub fn map_source_row_by_time(
    anchor_time: i64,
    src_times: &[i64],
    source_key: &str,
) -> Result<usize, QuantError> {
    if src_times.is_empty() {
        return Err(QuantError::InvalidParam(format!(
            "source '{source_key}' 的 time 列为空，无法做前序映射"
        )));
    }

    let end_exclusive = src_times.partition_point(|value| *value <= anchor_time);
    if end_exclusive == 0 {
        Err(QuantError::InvalidParam(format!(
            "anchor_time={anchor_time} 无法前序映射到 source '{source_key}'"
        )))
    } else {
        Ok(end_exclusive - 1)
    }
}

pub fn map_source_end_by_base_end(
    base_times: &[i64],
    src_times: &[i64],
    base_end_exclusive_idx: usize,
    source_key: &str,
) -> Result<usize, QuantError> {
    if base_end_exclusive_idx == 0 {
        return Ok(0);
    }
    if base_end_exclusive_idx > base_times.len() {
        return Err(QuantError::InvalidParam(format!(
            "base_end_exclusive_idx={} 越界，base_times.len()={}",
            base_end_exclusive_idx,
            base_times.len()
        )));
    }

    let anchor_time = base_times[base_end_exclusive_idx - 1];
    Ok(map_source_row_by_time(anchor_time, src_times, source_key)? + 1)
}

pub fn validate_coverage(
    base_times: &[i64],
    src_times: &[i64],
    source_interval_ms: i64,
    source_key: &str,
) -> Result<(), QuantError> {
    if base_times.is_empty() {
        return Ok(());
    }
    if src_times.is_empty() {
        return Err(QuantError::InvalidParam(format!(
            "source '{source_key}' 的 time 列为空，无法覆盖 base"
        )));
    }
    if source_interval_ms <= 0 {
        return Err(QuantError::InvalidParam(format!(
            "source '{source_key}' 的 source_interval_ms={} 非法",
            source_interval_ms
        )));
    }

    let base_start = base_times[0];
    let base_end = *base_times.last().expect("base_times 非空时 last 必然存在");
    let src_start = src_times[0];
    let src_end = *src_times.last().expect("src_times 非空时 last 必然存在");

    if src_start > base_start {
        return Err(QuantError::InvalidParam(format!(
            "source '{source_key}' 首覆盖失败：src_first={} > base_first={}",
            src_start, base_start
        )));
    }

    let src_end_exclusive = src_end.checked_add(source_interval_ms).ok_or_else(|| {
        QuantError::InvalidParam(format!("source '{source_key}' 的尾覆盖计算溢出"))
    })?;
    if src_end_exclusive <= base_end {
        return Err(QuantError::InvalidParam(format!(
            "source '{source_key}' 尾覆盖失败：src_last + interval = {} <= base_last={}",
            src_end_exclusive, base_end
        )));
    }

    Ok(())
}

/// 中文注释：这里统一生成单列 mapping，前提是 coverage 已经过严校验。
pub fn build_mapping_column_unchecked(
    base_times: &[i64],
    src_times: &[i64],
    source_key: &str,
) -> Result<Series, QuantError> {
    let mut mapped = Vec::with_capacity(base_times.len());
    for &anchor_time in base_times {
        mapped.push(map_source_row_by_time(anchor_time, src_times, source_key)? as u32);
    }
    Ok(Series::new(source_key.into(), mapped))
}

pub fn build_mapping_frame(
    source: &HashMap<String, DataFrame>,
    base_data_key: &str,
) -> Result<DataFrame, QuantError> {
    let base_df = source.get(base_data_key).ok_or_else(|| {
        QuantError::InvalidParam(format!("base_data_key '{base_data_key}' 不存在于 source"))
    })?;
    let base_times = extract_time_values(base_df, base_data_key)?;

    let mut columns = Vec::with_capacity(source.len() + 1);
    columns.push(Series::new("time".into(), base_times.clone()).into_column());

    let mut source_keys: Vec<&String> = source.keys().collect();
    source_keys.sort_unstable();
    for source_key in source_keys {
        let src_df = source
            .get(source_key)
            .ok_or_else(|| QuantError::InvalidParam(format!("source '{source_key}' 不存在")))?;
        let src_times = extract_time_values(src_df, source_key)?;

        let series = if source_key == base_data_key {
            let natural: Vec<u32> = (0..base_times.len()).map(|idx| idx as u32).collect();
            Series::new(source_key.as_str().into(), natural)
        } else {
            let interval_ms = resolve_source_interval_ms(source_key)?;
            validate_coverage(&base_times, &src_times, interval_ms, source_key)?;
            build_mapping_column_unchecked(&base_times, &src_times, source_key)?
        };
        columns.push(series.into_column());
    }

    let mapping = DataFrame::new(columns)?;
    let column_names = mapping.get_column_names();
    if column_names.first().map(|v| v.as_str()) != Some("time") {
        return Err(QuantError::InvalidParam(
            "mapping 第一列必须固定为 time".to_string(),
        ));
    }
    Ok(mapping)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def build_mapping_frame(
    source: dict[str, object],
    base_data_key: str,
) -> object:
    """按 DataPack contract 构建 mapping DataFrame"""
"#
)]
#[pyfunction(name = "build_mapping_frame")]
pub fn py_build_mapping_frame(
    source: HashMap<String, Bound<'_, PyAny>>,
    base_data_key: String,
) -> PyResult<PyDataFrame> {
    let mut source_inner = HashMap::new();
    for (key, value) in source {
        let df: PyDataFrame = value.extract()?;
        source_inner.insert(key, df.into());
    }
    Ok(PyDataFrame(build_mapping_frame(
        &source_inner,
        &base_data_key,
    )?))
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_build_mapping_frame, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_df(times: &[i64]) -> DataFrame {
        DataFrame::new(vec![Series::new("time".into(), times.to_vec()).into()]).expect("df 应成功")
    }

    #[test]
    fn test_extract_time_values_rejects_duplicate_time() {
        let df = build_df(&[0, 1, 1, 2]);
        let err = extract_time_values(&df, "ohlcv_1ms").expect_err("重复时间戳必须报错");
        assert!(format!("{err}").contains("严格递增"));
    }

    #[test]
    fn test_resolve_source_interval_ms_supports_formal_units() {
        assert_eq!(resolve_source_interval_ms("ohlcv_1ms").expect("1ms"), 1);
        assert_eq!(resolve_source_interval_ms("ohlcv_2s").expect("2s"), 2_000);
        assert_eq!(resolve_source_interval_ms("ohlcv_3m").expect("3m"), 180_000);
        assert_eq!(
            resolve_source_interval_ms("ohlcv_4h").expect("4h"),
            14_400_000
        );
        assert_eq!(
            resolve_source_interval_ms("ohlcv_5d").expect("5d"),
            432_000_000
        );
        assert_eq!(
            resolve_source_interval_ms("ohlcv_2w").expect("2w"),
            1_209_600_000
        );
        assert_eq!(
            resolve_source_interval_ms("ohlcv_1M").expect("1M"),
            2_419_200_000
        );
        assert_eq!(
            resolve_source_interval_ms("ohlcv_1y").expect("1y"),
            31_449_600_000
        );
    }
}
