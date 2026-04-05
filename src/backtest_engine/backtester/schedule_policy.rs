use crate::backtest_engine::backtester::schedule_contract::BacktestParamSegment;
use crate::error::{BacktestError, QuantError};
use crate::types::Param;

fn same_param(lhs: &Option<Param>, rhs: &Option<Param>) -> bool {
    match (lhs, rhs) {
        (None, None) => true,
        (Some(l), Some(r)) => {
            l.value == r.value
                && l.min == r.min
                && l.max == r.max
                && l.dtype == r.dtype
                && l.optimize == r.optimize
                && l.log_scale == r.log_scale
                && l.step == r.step
        }
        _ => false,
    }
}

/// 中文注释：字段级 policy 当前只锁死不允许跨段变化的资金与手续费字段。
pub fn validate_backtest_param_schedule_policy(
    schedule: &[BacktestParamSegment],
) -> Result<(), QuantError> {
    let first = schedule.first().ok_or_else(|| {
        QuantError::Backtest(BacktestError::ValidationError("schedule 不能为空".into()))
    })?;

    for (idx, segment) in schedule.iter().enumerate().skip(1) {
        let lhs = &first.params;
        let rhs = &segment.params;

        if lhs.initial_capital != rhs.initial_capital {
            return Err(BacktestError::ValidationError(format!(
                "initial_capital 不允许跨 segment 变化，idx={idx}, first={}, current={}",
                lhs.initial_capital, rhs.initial_capital
            ))
            .into());
        }
        if lhs.fee_fixed != rhs.fee_fixed {
            return Err(BacktestError::ValidationError(format!(
                "fee_fixed 不允许跨 segment 变化，idx={idx}, first={}, current={}",
                lhs.fee_fixed, rhs.fee_fixed
            ))
            .into());
        }
        if lhs.fee_pct != rhs.fee_pct {
            return Err(BacktestError::ValidationError(format!(
                "fee_pct 不允许跨 segment 变化，idx={idx}, first={}, current={}",
                lhs.fee_pct, rhs.fee_pct
            ))
            .into());
        }

        // 中文注释：显式触碰允许变化字段，避免后续误把它们当成默认“必须相等”。
        let _allowed_vary = (
            same_param(&lhs.sl_pct, &rhs.sl_pct),
            same_param(&lhs.tp_pct, &rhs.tp_pct),
            same_param(&lhs.tsl_pct, &rhs.tsl_pct),
            same_param(&lhs.sl_atr, &rhs.sl_atr),
            same_param(&lhs.tp_atr, &rhs.tp_atr),
            same_param(&lhs.tsl_atr, &rhs.tsl_atr),
            same_param(&lhs.atr_period, &rhs.atr_period),
            same_param(&lhs.tsl_psar_af0, &rhs.tsl_psar_af0),
            same_param(&lhs.tsl_psar_af_step, &rhs.tsl_psar_af_step),
            same_param(&lhs.tsl_psar_max_af, &rhs.tsl_psar_max_af),
            lhs.tsl_atr_tight == rhs.tsl_atr_tight,
            lhs.sl_exit_in_bar == rhs.sl_exit_in_bar,
            lhs.tp_exit_in_bar == rhs.tp_exit_in_bar,
            lhs.sl_trigger_mode == rhs.sl_trigger_mode,
            lhs.tp_trigger_mode == rhs.tp_trigger_mode,
            lhs.tsl_trigger_mode == rhs.tsl_trigger_mode,
            lhs.sl_anchor_mode == rhs.sl_anchor_mode,
            lhs.tp_anchor_mode == rhs.tp_anchor_mode,
            lhs.tsl_anchor_mode == rhs.tsl_anchor_mode,
        );
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{BacktestParams, Param, ParamType};

    fn params() -> BacktestParams {
        BacktestParams::default()
    }

    #[test]
    fn test_validate_backtest_param_schedule_policy_contract() {
        let mut second = params();
        second.sl_pct = Some(Param::new(
            1.0,
            None,
            None,
            Some(ParamType::Float),
            false,
            false,
            0.01,
        ));
        let ok = vec![
            BacktestParamSegment::new(0, 2, params()),
            BacktestParamSegment::new(2, 4, second),
        ];
        validate_backtest_param_schedule_policy(&ok).expect("允许变化字段应通过");

        let mut bad_params = params();
        bad_params.initial_capital = 20_000.0;
        let bad = vec![
            BacktestParamSegment::new(0, 2, params()),
            BacktestParamSegment::new(2, 4, bad_params),
        ];
        assert!(validate_backtest_param_schedule_policy(&bad).is_err());
    }
}
