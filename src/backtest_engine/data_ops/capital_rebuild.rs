use crate::error::QuantError;
use polars::prelude::*;
use std::collections::HashSet;

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
    rebuild_capital_columns_for_stitched_backtest_with_boundaries(backtest_df, initial_capital, &[])
}

/// stitched 回测资金列重建（支持窗口边界）。
///
/// 说明：
/// 1. `boundary_starts` 传入每个窗口（除第一个外）在 stitched dataframe 中的起始行索引；
/// 2. 在这些边界行，强制 growth=1，避免把“窗口局部资金重置”误判为真实回撤；
/// 3. 窗口内部仍按局部资金列增长因子重建，保持原始口径。
pub fn rebuild_capital_columns_for_stitched_backtest_with_boundaries(
    backtest_df: &DataFrame,
    initial_capital: f64,
    boundary_starts: &[usize],
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
    let boundary_set: HashSet<usize> = boundary_starts
        .iter()
        .copied()
        .filter(|&idx| idx > 0 && idx < n)
        .collect();

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

        let (growth_bal, growth_eq) = if boundary_set.contains(&i) {
            // 中文注释：窗口边界行不跨窗口取比值，避免拼接伪回撤。
            (1.0_f64, 1.0_f64)
        } else {
            let gb = if prev_bal_local > 0.0 {
                curr_bal_local / prev_bal_local
            } else if curr_bal_local == 0.0 {
                0.0
            } else {
                return Err(QuantError::InvalidParam(format!(
                    "balance 增长因子非法: idx={i}, prev=0 curr={curr_bal_local}"
                )));
            };
            let ge = if prev_eq_local > 0.0 {
                curr_eq_local / prev_eq_local
            } else if curr_eq_local == 0.0 {
                0.0
            } else {
                return Err(QuantError::InvalidParam(format!(
                    "equity 增长因子非法: idx={i}, prev=0 curr={curr_eq_local}"
                )));
            };
            (gb, ge)
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
