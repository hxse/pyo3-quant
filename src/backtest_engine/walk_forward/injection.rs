use crate::error::{OptimizerError, QuantError};
use polars::prelude::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CrossSide {
    Long,
    Short,
}

/// 中文注释：窗口注入只改测试 active 首根 carry 开仓，以及测试 active 段倒数第二根强平。
pub(crate) fn build_carry_only_signals_for_window(
    signals_df: &DataFrame,
    test_warmup_bars: usize,
    test_active_bars: usize,
    prev_test_last_position: Option<CrossSide>,
) -> Result<DataFrame, QuantError> {
    if test_warmup_bars < 1 {
        return Err(OptimizerError::InvalidConfig("test_warmup_bars must be >= 1".into()).into());
    }
    if test_active_bars < 2 {
        return Err(OptimizerError::InvalidConfig(
            "test_active_bars must be >= 2 for boundary signal injection".into(),
        )
        .into());
    }

    let expected_len = test_warmup_bars + test_active_bars;
    if signals_df.height() != expected_len {
        return Err(OptimizerError::InvalidConfig(format!(
            "eval length mismatch: signals={}, expected={}",
            signals_df.height(),
            expected_len
        ))
        .into());
    }

    let mut entry_long = bool_vec_from_column(signals_df, "entry_long")?;
    let mut exit_long = bool_vec_from_column(signals_df, "exit_long")?;
    let mut entry_short = bool_vec_from_column(signals_df, "entry_short")?;
    let mut exit_short = bool_vec_from_column(signals_df, "exit_short")?;

    let test_pack_active_first_idx = test_warmup_bars;
    if let Some(ref side) = prev_test_last_position {
        match side {
            CrossSide::Long => {
                entry_long[test_pack_active_first_idx] = true;
                entry_short[test_pack_active_first_idx] = false;
                exit_long[test_pack_active_first_idx] = false;
                exit_short[test_pack_active_first_idx] = false;
            }
            CrossSide::Short => {
                entry_long[test_pack_active_first_idx] = false;
                entry_short[test_pack_active_first_idx] = true;
                exit_long[test_pack_active_first_idx] = false;
                exit_short[test_pack_active_first_idx] = false;
            }
        }
    }

    let mut out = signals_df.clone();
    out.with_column(Series::new("entry_long".into(), entry_long))?;
    out.with_column(Series::new("exit_long".into(), exit_long))?;
    out.with_column(Series::new("entry_short".into(), entry_short))?;
    out.with_column(Series::new("exit_short".into(), exit_short))?;
    Ok(out)
}

/// 中文注释：正式窗口结果在 carry-only 信号基础上追加尾部强平，供公开 test_pack_result 使用。
pub(crate) fn build_final_signals_for_window(
    carry_only_signals_df: &DataFrame,
    test_warmup_bars: usize,
    test_active_bars: usize,
) -> Result<DataFrame, QuantError> {
    if test_warmup_bars < 1 {
        return Err(OptimizerError::InvalidConfig("test_warmup_bars must be >= 1".into()).into());
    }
    if test_active_bars < 2 {
        return Err(OptimizerError::InvalidConfig(
            "test_active_bars must be >= 2 for boundary signal injection".into(),
        )
        .into());
    }

    let expected_len = test_warmup_bars + test_active_bars;
    if carry_only_signals_df.height() != expected_len {
        return Err(OptimizerError::InvalidConfig(format!(
            "eval length mismatch: signals={}, expected={}",
            carry_only_signals_df.height(),
            expected_len
        ))
        .into());
    }

    let mut entry_long = bool_vec_from_column(carry_only_signals_df, "entry_long")?;
    let mut exit_long = bool_vec_from_column(carry_only_signals_df, "exit_long")?;
    let mut entry_short = bool_vec_from_column(carry_only_signals_df, "entry_short")?;
    let mut exit_short = bool_vec_from_column(carry_only_signals_df, "exit_short")?;
    let test_exit_idx = test_warmup_bars + test_active_bars - 2;
    entry_long[test_exit_idx] = false;
    exit_long[test_exit_idx] = true;
    entry_short[test_exit_idx] = false;
    exit_short[test_exit_idx] = true;

    let mut out = carry_only_signals_df.clone();
    out.with_column(Series::new("entry_long".into(), entry_long))?;
    out.with_column(Series::new("exit_long".into(), exit_long))?;
    out.with_column(Series::new("entry_short".into(), entry_short))?;
    out.with_column(Series::new("exit_short".into(), exit_short))?;
    Ok(out)
}

fn bool_vec_from_column(df: &DataFrame, col_name: &str) -> Result<Vec<bool>, QuantError> {
    let col = df.column(col_name).map_err(|_| {
        OptimizerError::InvalidConfig(format!("signals missing required column: {col_name}"))
    })?;
    let ca = col.bool().map_err(|_| {
        OptimizerError::InvalidConfig(format!("signals column must be bool: {col_name}"))
    })?;
    Ok(ca.into_iter().map(|v| v.unwrap_or(false)).collect())
}

/// 中文注释：跨窗继承方向只看“上一窗测试段最后一根是否仍有未平仓位”。
pub(crate) fn detect_cross_boundary_side_at(
    backtest_df: &DataFrame,
    boundary_idx: usize,
) -> Result<Option<CrossSide>, QuantError> {
    let entry_long = backtest_df.column("entry_long_price")?.f64()?;
    let exit_long = backtest_df.column("exit_long_price")?.f64()?;
    let entry_short = backtest_df.column("entry_short_price")?.f64()?;
    let exit_short = backtest_df.column("exit_short_price")?.f64()?;

    let el = entry_long.get(boundary_idx).unwrap_or(f64::NAN);
    let xl = exit_long.get(boundary_idx).unwrap_or(f64::NAN);
    let es = entry_short.get(boundary_idx).unwrap_or(f64::NAN);
    let xs = exit_short.get(boundary_idx).unwrap_or(f64::NAN);

    let long_cross = !el.is_nan() && xl.is_nan();
    let short_cross = !es.is_nan() && xs.is_nan();

    if long_cross && short_cross {
        return Err(OptimizerError::InvalidConfig(format!(
            "cross-boundary side conflict at idx={boundary_idx}: both long and short active"
        ))
        .into());
    }
    if long_cross {
        return Ok(Some(CrossSide::Long));
    }
    if short_cross {
        return Ok(Some(CrossSide::Short));
    }
    Ok(None)
}

/// 中文注释：自然回放的末根状态是下一窗口 carry 的唯一来源。
pub(crate) fn detect_last_bar_position(
    backtest_df: &DataFrame,
) -> Result<Option<CrossSide>, QuantError> {
    if backtest_df.height() == 0 {
        return Err(OptimizerError::InvalidConfig(
            "cross-boundary detection requires non-empty backtest".into(),
        )
        .into());
    }
    detect_cross_boundary_side_at(backtest_df, backtest_df.height() - 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_signals_df() -> DataFrame {
        DataFrame::new(vec![
            Series::new("entry_long".into(), vec![true, true, false, false, false]).into(),
            Series::new("exit_long".into(), vec![false, false, false, false, false]).into(),
            Series::new("entry_short".into(), vec![false, false, true, false, false]).into(),
            Series::new("exit_short".into(), vec![false, false, false, false, false]).into(),
        ])
        .expect("signals df 应成功")
    }

    #[test]
    fn test_wf_signal_injection_contract() {
        let df = build_signals_df();
        let carry_only = build_carry_only_signals_for_window(&df, 2, 3, Some(CrossSide::Long))
            .expect("carry-only 注入应成功");
        let out = build_final_signals_for_window(&carry_only, 2, 3).expect("正式信号注入应成功");

        assert_eq!(
            out.column("entry_long")
                .expect("entry_long")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![true, true, true, false, false]
        );
        assert_eq!(
            out.column("entry_short")
                .expect("entry_short")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![false, false, false, false, false]
        );
        assert_eq!(
            out.column("exit_long")
                .expect("exit_long")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![false, false, false, true, false]
        );
        assert_eq!(
            out.column("exit_short")
                .expect("exit_short")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![false, false, false, true, false]
        );
    }

    #[test]
    fn test_carry_only_signals_do_not_force_flatten() {
        let df = build_signals_df();
        let carry_only = build_carry_only_signals_for_window(&df, 2, 3, Some(CrossSide::Long))
            .expect("carry-only 注入应成功");

        assert_eq!(
            carry_only
                .column("exit_long")
                .expect("exit_long")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![false, false, false, false, false]
        );
        assert_eq!(
            carry_only
                .column("exit_short")
                .expect("exit_short")
                .bool()
                .expect("bool")
                .into_iter()
                .map(|v| v.unwrap_or(false))
                .collect::<Vec<_>>(),
            vec![false, false, false, false, false]
        );
    }

    #[test]
    fn test_carry_only_signals_keep_raw_signals_when_prev_position_is_none() {
        let df = build_signals_df();
        let carry_only = build_carry_only_signals_for_window(&df, 2, 3, None)
            .expect("carry-only 无持仓路径应成功");

        for column_name in ["entry_long", "exit_long", "entry_short", "exit_short"] {
            assert_eq!(
                carry_only
                    .column(column_name)
                    .expect("carry col")
                    .bool()
                    .expect("bool")
                    .into_iter()
                    .map(|v| v.unwrap_or(false))
                    .collect::<Vec<_>>(),
                df.column(column_name)
                    .expect("raw col")
                    .bool()
                    .expect("bool")
                    .into_iter()
                    .map(|v| v.unwrap_or(false))
                    .collect::<Vec<_>>()
            );
        }
    }
}
