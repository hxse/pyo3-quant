use crate::error::{OptimizerError, QuantError};
use polars::prelude::*;

pub(super) fn ensure_same_schema(
    left: &DataFrame,
    right: &DataFrame,
    name: &str,
) -> Result<(), QuantError> {
    if left.get_column_names() != right.get_column_names() || left.dtypes() != right.dtypes() {
        return Err(OptimizerError::InvalidConfig(format!("{name} schema 不一致")).into());
    }
    Ok(())
}

pub(super) fn vstack_dfs_strict(dfs: &[DataFrame], name: &str) -> Result<DataFrame, QuantError> {
    let first = dfs
        .first()
        .ok_or_else(|| OptimizerError::InvalidConfig(format!("{name} 为空，无法拼接")))?;
    let mut out = first.clone();
    for df in dfs.iter().skip(1) {
        ensure_same_schema(&out, df, name)?;
        out.vstack_mut(df)?;
    }
    Ok(out)
}

pub(super) fn first_time(df: &DataFrame, context: &str) -> Result<i64, QuantError> {
    nth_time(df, 0, context)
}

pub(super) fn last_time(df: &DataFrame, context: &str) -> Result<i64, QuantError> {
    let idx = df
        .height()
        .checked_sub(1)
        .ok_or_else(|| OptimizerError::InvalidConfig(format!("{context} 为空")))?;
    nth_time(df, idx, context)
}

pub(super) fn nth_time(df: &DataFrame, idx: usize, context: &str) -> Result<i64, QuantError> {
    let time = df
        .column("time")
        .map_err(|_| OptimizerError::InvalidConfig(format!("{context} 缺少 time 列")))?;
    let time = time
        .i64()
        .map_err(|_| OptimizerError::InvalidConfig(format!("{context}.time 必须是 Int64")))?;
    time.get(idx).ok_or_else(|| {
        OptimizerError::InvalidConfig(format!("{context}.time 在 idx={} 为空", idx)).into()
    })
}
