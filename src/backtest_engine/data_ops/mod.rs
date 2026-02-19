use crate::error::QuantError;
use crate::types::{BacktestSummary, DataContainer, IndicatorResults};
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

fn validate_slice_bounds(
    height: usize,
    start: usize,
    len: usize,
    name: &str,
) -> Result<(), QuantError> {
    if len == 0 {
        return Err(QuantError::InvalidParam(format!(
            "{name} 切片长度 len 必须 > 0"
        )));
    }
    if start >= height || start + len > height {
        return Err(QuantError::InvalidParam(format!(
            "{name} 切片越界: height={height}, start={start}, len={len}"
        )));
    }
    Ok(())
}

fn schemas_equal(left: &DataFrame, right: &DataFrame) -> bool {
    if left.width() != right.width() {
        return false;
    }
    let l_names = left.get_column_names();
    let r_names = right.get_column_names();
    if l_names != r_names {
        return false;
    }
    let l_dtypes = left.dtypes();
    let r_dtypes = right.dtypes();
    l_dtypes == r_dtypes
}

fn vstack_dfs_strict(dfs: &[DataFrame], name: &str) -> Result<DataFrame, QuantError> {
    let first = dfs
        .first()
        .ok_or_else(|| QuantError::InvalidParam(format!("{name} 为空，无法拼接")))?;
    let mut out = first.clone();
    for (idx, df) in dfs.iter().enumerate().skip(1) {
        if !schemas_equal(&out, df) {
            return Err(QuantError::InvalidParam(format!(
                "{name} schema 不一致，idx={idx} 无法拼接"
            )));
        }
        out.vstack_mut(df).map_err(QuantError::from)?;
    }
    Ok(out)
}

/// 按 base 窗口切片 BacktestSummary（含 indicators mapping 语义切片）。
pub fn slice_backtest_summary_by_base_window(
    summary: &BacktestSummary,
    data: &DataContainer,
    start: usize,
    len: usize,
) -> Result<BacktestSummary, QuantError> {
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| QuantError::InvalidParam("base_data_key 不存在于 source".to_string()))?;
    validate_slice_bounds(base_df.height(), start, len, "BacktestSummary")?;

    let indicators = match &summary.indicators {
        Some(ind_map) => {
            // 中文注释：indicators 与 source 同样是多周期 DataFrame，复用 DataContainer 切片逻辑保持 mapping 一致。
            let fake = DataContainer {
                mapping: data.mapping.clone(),
                skip_mask: None,
                source: ind_map.clone(),
                base_data_key: data.base_data_key.clone(),
            };
            let sliced = slice_data_container_by_base_window(&fake, start, len)?;
            Some(sliced.source)
        }
        None => None,
    };

    let signals = match &summary.signals {
        Some(df) => {
            validate_slice_bounds(df.height(), start, len, "signals")?;
            Some(df.slice(start as i64, len))
        }
        None => None,
    };
    let backtest = match &summary.backtest {
        Some(df) => {
            validate_slice_bounds(df.height(), start, len, "backtest")?;
            Some(df.slice(start as i64, len))
        }
        None => None,
    };

    Ok(BacktestSummary {
        indicators,
        signals,
        backtest,
        // 中文注释：切片后绩效必须按 test-only 重新计算，这里不沿用旧值。
        performance: None,
    })
}

/// 严格拼接多个窗口 BacktestSummary（不拼接 performance）。
pub fn concat_backtest_summaries(
    summaries: &[BacktestSummary],
) -> Result<BacktestSummary, QuantError> {
    let first = summaries
        .first()
        .ok_or_else(|| QuantError::InvalidParam("summaries 为空，无法拼接".to_string()))?;

    let indicators = match &first.indicators {
        Some(first_map) => {
            let mut keys: Vec<String> = first_map.keys().cloned().collect();
            keys.sort_unstable();
            let mut out: IndicatorResults = HashMap::new();

            for key in keys {
                let mut per_key: Vec<DataFrame> = Vec::with_capacity(summaries.len());
                for (idx, s) in summaries.iter().enumerate() {
                    let map = s.indicators.as_ref().ok_or_else(|| {
                        QuantError::InvalidParam(format!(
                            "indicators 缺失，idx={idx} 无法完成严格拼接"
                        ))
                    })?;
                    let df = map.get(&key).ok_or_else(|| {
                        QuantError::InvalidParam(format!(
                            "indicators key 缺失: key={key}, idx={idx}"
                        ))
                    })?;
                    per_key.push(df.clone());
                }
                out.insert(
                    key.clone(),
                    vstack_dfs_strict(&per_key, &format!("indicators[{key}]"))?,
                );
            }
            Some(out)
        }
        None => None,
    };

    let signals = match &first.signals {
        Some(_) => {
            let mut all = Vec::with_capacity(summaries.len());
            for (idx, s) in summaries.iter().enumerate() {
                let df = s.signals.as_ref().ok_or_else(|| {
                    QuantError::InvalidParam(format!("signals 缺失，idx={idx} 无法拼接"))
                })?;
                all.push(df.clone());
            }
            Some(vstack_dfs_strict(&all, "signals")?)
        }
        None => None,
    };

    let backtest = match &first.backtest {
        Some(_) => {
            let mut all = Vec::with_capacity(summaries.len());
            for (idx, s) in summaries.iter().enumerate() {
                let df = s.backtest.as_ref().ok_or_else(|| {
                    QuantError::InvalidParam(format!("backtest 缺失，idx={idx} 无法拼接"))
                })?;
                all.push(df.clone());
            }
            Some(vstack_dfs_strict(&all, "backtest")?)
        }
        None => None,
    };

    Ok(BacktestSummary {
        indicators,
        signals,
        backtest,
        performance: None,
    })
}

fn validate_local_capital(v: f64, name: &str, idx: usize) -> Result<(), QuantError> {
    if !v.is_finite() {
        return Err(QuantError::InvalidParam(format!(
            "{name} 非法: idx={idx} 出现非有限值 {v}"
        )));
    }
    if v < 0.0 {
        return Err(QuantError::InvalidParam(format!(
            "{name} 非法: idx={idx} 出现负值 {v}"
        )));
    }
    Ok(())
}

/// stitched 回测资金列重建（唯一口径：基于局部资金列增长因子）。
pub fn rebuild_capital_columns_for_stitched_backtest(
    backtest_df: &DataFrame,
    initial_capital: f64,
) -> Result<DataFrame, QuantError> {
    if initial_capital <= 0.0 {
        return Err(QuantError::InvalidParam(format!(
            "initial_capital 必须 > 0，当前={initial_capital}"
        )));
    }
    let n = backtest_df.height();
    if n == 0 {
        return Err(QuantError::InvalidParam(
            "backtest_df 为空，无法重建资金列".to_string(),
        ));
    }

    let balance_local = backtest_df.column("balance")?.f64()?;
    let equity_local = backtest_df.column("equity")?.f64()?;
    let fee_local = backtest_df.column("fee")?.f64()?;

    let mut balance = vec![0.0_f64; n];
    let mut equity = vec![0.0_f64; n];
    let mut total_return_pct = vec![0.0_f64; n];
    let mut fee_cum = vec![0.0_f64; n];
    let mut current_drawdown = vec![0.0_f64; n];

    let mut peak_equity = initial_capital;
    let fee0 = fee_local.get(0).unwrap_or(0.0);
    validate_local_capital(fee0, "fee_local", 0)?;

    balance[0] = initial_capital;
    equity[0] = initial_capital;
    total_return_pct[0] = 0.0;
    fee_cum[0] = fee0;
    current_drawdown[0] = 0.0;

    for i in 1..n {
        let prev_bal_local = balance_local.get(i - 1).unwrap_or(f64::NAN);
        let curr_bal_local = balance_local.get(i).unwrap_or(f64::NAN);
        let prev_eq_local = equity_local.get(i - 1).unwrap_or(f64::NAN);
        let curr_eq_local = equity_local.get(i).unwrap_or(f64::NAN);
        let curr_fee = fee_local.get(i).unwrap_or(f64::NAN);

        validate_local_capital(prev_bal_local, "balance_local_prev", i - 1)?;
        validate_local_capital(curr_bal_local, "balance_local_curr", i)?;
        validate_local_capital(prev_eq_local, "equity_local_prev", i - 1)?;
        validate_local_capital(curr_eq_local, "equity_local_curr", i)?;
        validate_local_capital(curr_fee, "fee_local", i)?;

        let growth_bal = if prev_bal_local > 0.0 {
            curr_bal_local / prev_bal_local
        } else if curr_bal_local == 0.0 {
            0.0
        } else {
            return Err(QuantError::InvalidParam(format!(
                "balance 增长因子非法: idx={i}, prev=0 curr={curr_bal_local}"
            )));
        };
        let growth_eq = if prev_eq_local > 0.0 {
            curr_eq_local / prev_eq_local
        } else if curr_eq_local == 0.0 {
            0.0
        } else {
            return Err(QuantError::InvalidParam(format!(
                "equity 增长因子非法: idx={i}, prev=0 curr={curr_eq_local}"
            )));
        };

        if !growth_bal.is_finite() || growth_bal < 0.0 {
            return Err(QuantError::InvalidParam(format!(
                "balance 增长因子非法: idx={i}, growth={growth_bal}"
            )));
        }
        if !growth_eq.is_finite() || growth_eq < 0.0 {
            return Err(QuantError::InvalidParam(format!(
                "equity 增长因子非法: idx={i}, growth={growth_eq}"
            )));
        }

        balance[i] = balance[i - 1] * growth_bal;
        equity[i] = equity[i - 1] * growth_eq;
        total_return_pct[i] = equity[i] / initial_capital - 1.0;
        fee_cum[i] = fee_cum[i - 1] + curr_fee;

        if equity[i] > peak_equity {
            peak_equity = equity[i];
        }
        current_drawdown[i] = if peak_equity > 0.0 {
            1.0 - (equity[i] / peak_equity)
        } else {
            0.0
        };
    }

    let mut out = backtest_df.clone();
    out.with_column(Series::new("balance".into(), balance))?;
    out.with_column(Series::new("equity".into(), equity))?;
    out.with_column(Series::new("total_return_pct".into(), total_return_pct))?;
    out.with_column(Series::new("fee_cum".into(), fee_cum))?;
    out.with_column(Series::new("current_drawdown".into(), current_drawdown))?;
    Ok(out)
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
    align_to_base_range: bool = False,
) -> pyo3_quant.DataContainer:
    """在 Rust 端构建 DataContainer.mapping（可选按 base 时间范围对齐）"""
"#
)]
#[pyfunction(name = "build_time_mapping")]
#[pyo3(signature = (data_dict, align_to_base_range=false))]
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

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def slice_backtest_summary(
    summary: pyo3_quant.BacktestSummary,
    data_dict: pyo3_quant.DataContainer,
    start: int,
    length: int,
) -> pyo3_quant.BacktestSummary:
    """按 base 窗口切 BacktestSummary（含 indicators mapping 语义）"""
"#
)]
#[pyfunction(name = "slice_backtest_summary")]
pub fn py_slice_backtest_summary(
    summary: BacktestSummary,
    data_dict: DataContainer,
    start: usize,
    length: usize,
) -> PyResult<BacktestSummary> {
    slice_backtest_summary_by_base_window(&summary, &data_dict, start, length).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def concat_backtest_summaries(
    summaries: list[pyo3_quant.BacktestSummary],
) -> pyo3_quant.BacktestSummary:
    """严格拼接多个 BacktestSummary（不拼接 performance）"""
"#
)]
#[pyfunction(name = "concat_backtest_summaries")]
pub fn py_concat_backtest_summaries(summaries: Vec<BacktestSummary>) -> PyResult<BacktestSummary> {
    concat_backtest_summaries(&summaries).map_err(Into::into)
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
    m.add_function(wrap_pyfunction!(py_build_time_mapping, m)?)?;
    m.add_function(wrap_pyfunction!(py_slice_data_container, m)?)?;
    m.add_function(wrap_pyfunction!(py_is_natural_mapping_column, m)?)?;
    m.add_function(wrap_pyfunction!(py_slice_backtest_summary, m)?)?;
    m.add_function(wrap_pyfunction!(py_concat_backtest_summaries, m)?)?;
    m.add_function(wrap_pyfunction!(py_rebuild_stitched_capital_columns, m)?)?;
    Ok(())
}
