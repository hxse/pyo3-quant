use crate::backtest_engine::indicators::atr::atr_required_warmup_bars;
use crate::backtest_engine::indicators::contracts::resolve_indicator_contracts;
use crate::backtest_engine::indicators::psar::psar_required_warmup_bars;
use crate::error::QuantError;
use crate::types::{BacktestParams, IndicatorsParams, Param};
use std::collections::HashMap;

/// 中文注释：A1 先把共享 warmup 真值链收敛成单一对象，后续 planner/WF 直接消费。
#[derive(Debug, Clone, Default)]
pub struct WarmupRequirements {
    pub resolved_contract_warmup_by_key: HashMap<String, usize>,
    pub normalized_contract_warmup_by_key: HashMap<String, usize>,
    pub applied_contract_warmup_by_key: HashMap<String, usize>,
    pub backtest_exec_warmup_base: usize,
    pub required_warmup_by_key: HashMap<String, usize>,
}

pub fn resolve_contract_warmup_by_key(
    indicators_params: &IndicatorsParams,
) -> Result<HashMap<String, usize>, QuantError> {
    Ok(resolve_indicator_contracts(indicators_params)?.warmup_bars_by_source)
}

pub fn normalize_contract_warmup_by_key(
    source_keys: &[String],
    resolved_contract_warmup_by_key: &HashMap<String, usize>,
) -> HashMap<String, usize> {
    source_keys
        .iter()
        .map(|source_key| {
            (
                source_key.clone(),
                resolved_contract_warmup_by_key
                    .get(source_key)
                    .copied()
                    .unwrap_or(0),
            )
        })
        .collect()
}

pub fn apply_wf_warmup_policy(
    normalized_contract_warmup_by_key: &HashMap<String, usize>,
    ignore_indicator_warmup: bool,
) -> HashMap<String, usize> {
    normalized_contract_warmup_by_key
        .iter()
        .map(|(source_key, warmup_bars)| {
            (
                source_key.clone(),
                if ignore_indicator_warmup {
                    0
                } else {
                    *warmup_bars
                },
            )
        })
        .collect()
}

fn resolve_param_value(param: &Param, field_name: &str) -> Result<usize, QuantError> {
    let raw_value = if param.optimize {
        param.max
    } else {
        param.value
    };
    if !raw_value.is_finite() || raw_value < 0.0 {
        return Err(QuantError::InvalidParam(format!(
            "参数 '{field_name}' 解析出的 warmup 值非法：{raw_value}"
        )));
    }
    Ok(raw_value as usize)
}

pub fn resolve_backtest_exec_warmup_base(
    backtest_params: &BacktestParams,
) -> Result<usize, QuantError> {
    let uses_atr = backtest_params.is_sl_atr_param_valid()
        || backtest_params.is_tp_atr_param_valid()
        || backtest_params.is_tsl_atr_param_valid();
    let atr_warmup = if uses_atr {
        let atr_period = backtest_params.atr_period.as_ref().ok_or_else(|| {
            QuantError::InvalidParam("启用 ATR 风控时 atr_period 不能为空".to_string())
        })?;
        atr_required_warmup_bars(resolve_param_value(atr_period, "atr_period")?)
    } else {
        0
    };

    let psar_warmup = if backtest_params.is_tsl_psar_param_valid() {
        psar_required_warmup_bars()
    } else {
        0
    };

    Ok(atr_warmup.max(psar_warmup))
}

pub fn merge_required_warmup_by_key(
    base_data_key: &str,
    applied_contract_warmup_by_key: &HashMap<String, usize>,
    backtest_exec_warmup_base: usize,
) -> HashMap<String, usize> {
    applied_contract_warmup_by_key
        .iter()
        .map(|(source_key, warmup_bars)| {
            let merged = if source_key == base_data_key {
                (*warmup_bars).max(backtest_exec_warmup_base)
            } else {
                *warmup_bars
            };
            (source_key.clone(), merged)
        })
        .collect()
}

pub fn build_warmup_requirements(
    source_keys: &[String],
    base_data_key: &str,
    indicators_params: &IndicatorsParams,
    ignore_indicator_warmup: bool,
    backtest_params: &BacktestParams,
) -> Result<WarmupRequirements, QuantError> {
    let resolved_contract_warmup_by_key = resolve_contract_warmup_by_key(indicators_params)?;
    let normalized_contract_warmup_by_key =
        normalize_contract_warmup_by_key(source_keys, &resolved_contract_warmup_by_key);
    let applied_contract_warmup_by_key =
        apply_wf_warmup_policy(&normalized_contract_warmup_by_key, ignore_indicator_warmup);
    let backtest_exec_warmup_base = resolve_backtest_exec_warmup_base(backtest_params)?;
    let required_warmup_by_key = merge_required_warmup_by_key(
        base_data_key,
        &applied_contract_warmup_by_key,
        backtest_exec_warmup_base,
    );

    Ok(WarmupRequirements {
        resolved_contract_warmup_by_key,
        normalized_contract_warmup_by_key,
        applied_contract_warmup_by_key,
        backtest_exec_warmup_base,
        required_warmup_by_key,
    })
}

#[cfg(test)]
mod tests {
    use super::{
        apply_wf_warmup_policy, build_warmup_requirements, merge_required_warmup_by_key,
        resolve_backtest_exec_warmup_base,
    };
    use crate::types::{BacktestParams, Param, ParamType};
    use std::collections::HashMap;

    fn float_param(value: f64) -> Param {
        Param::new(
            value,
            None,
            None,
            Some(ParamType::Float),
            false,
            false,
            0.01,
        )
    }

    fn int_param(value: f64, max: Option<f64>, optimize: bool) -> Param {
        Param::new(
            value,
            None,
            max,
            Some(ParamType::Integer),
            optimize,
            false,
            1.0,
        )
    }

    #[test]
    fn test_ignore_indicator_warmup_contract() {
        let normalized = HashMap::from([
            ("ohlcv_15m".to_string(), 48_usize),
            ("ohlcv_1h".to_string(), 12_usize),
        ]);

        let kept = apply_wf_warmup_policy(&normalized, false);
        assert_eq!(kept, normalized);

        let ignored = apply_wf_warmup_policy(&normalized, true);
        assert_eq!(ignored.get("ohlcv_15m"), Some(&0));
        assert_eq!(ignored.get("ohlcv_1h"), Some(&0));
    }

    #[test]
    fn test_resolve_backtest_exec_warmup_base_uses_param_value_when_not_optimizing() {
        let mut params = BacktestParams::default();
        params.sl_atr = Some(float_param(1.5));
        params.atr_period = Some(int_param(7.0, Some(11.0), false));

        let warmup = resolve_backtest_exec_warmup_base(&params).expect("warmup 解析应成功");
        assert_eq!(warmup, 7);
    }

    #[test]
    fn test_resolve_backtest_exec_warmup_base_uses_param_max_when_optimizing() {
        let mut params = BacktestParams::default();
        params.sl_atr = Some(float_param(1.5));
        params.atr_period = Some(int_param(5.0, Some(11.0), true));
        params.tsl_psar_af0 = Some(float_param(0.02));
        params.tsl_psar_af_step = Some(float_param(0.02));
        params.tsl_psar_max_af = Some(float_param(0.2));

        let warmup = resolve_backtest_exec_warmup_base(&params).expect("warmup 解析应成功");
        assert_eq!(warmup, 11);
    }

    #[test]
    fn test_resolve_backtest_exec_warmup_base_rejects_missing_atr_period() {
        let mut params = BacktestParams::default();
        params.sl_atr = Some(float_param(1.5));

        let err = resolve_backtest_exec_warmup_base(&params).expect_err("缺少 atr_period 应失败");
        assert!(
            err.to_string().contains("atr_period"),
            "错误信息必须指向 atr_period，实际={err}"
        );
    }

    #[test]
    fn test_merge_required_warmup_by_key_only_overrides_base() {
        let merged = merge_required_warmup_by_key(
            "ohlcv_15m",
            &HashMap::from([
                ("ohlcv_15m".to_string(), 4_usize),
                ("ohlcv_1h".to_string(), 9_usize),
            ]),
            7,
        );

        assert_eq!(merged.get("ohlcv_15m"), Some(&7));
        assert_eq!(merged.get("ohlcv_1h"), Some(&9));
    }

    #[test]
    fn test_build_warmup_requirements_contract() {
        let source_keys = vec!["ohlcv_15m".to_string(), "ohlcv_1h".to_string()];
        let indicators_params = HashMap::from([(
            "ohlcv_15m".to_string(),
            HashMap::from([(
                "atr_0".to_string(),
                HashMap::from([("period".to_string(), int_param(14.0, None, false))]),
            )]),
        )]);
        let mut backtest_params = BacktestParams::default();
        backtest_params.sl_atr = Some(float_param(1.5));
        backtest_params.atr_period = Some(int_param(7.0, Some(9.0), false));

        let requirements = build_warmup_requirements(
            &source_keys,
            "ohlcv_15m",
            &indicators_params,
            true,
            &backtest_params,
        )
        .expect("warmup requirements 应成功");

        assert_eq!(
            requirements
                .resolved_contract_warmup_by_key
                .get("ohlcv_15m"),
            Some(&14)
        );
        assert_eq!(
            requirements
                .normalized_contract_warmup_by_key
                .get("ohlcv_15m"),
            Some(&14)
        );
        assert_eq!(
            requirements
                .normalized_contract_warmup_by_key
                .get("ohlcv_1h"),
            Some(&0)
        );
        assert_eq!(
            requirements.applied_contract_warmup_by_key.get("ohlcv_15m"),
            Some(&0)
        );
        assert_eq!(requirements.backtest_exec_warmup_base, 7);
        assert_eq!(
            requirements.required_warmup_by_key.get("ohlcv_15m"),
            Some(&7)
        );
        assert_eq!(
            requirements.required_warmup_by_key.get("ohlcv_1h"),
            Some(&0)
        );
    }
}
