use super::registry::{get_indicator_registry, resolve_param_value, WarmupMode};
use crate::error::{IndicatorError, QuantError};
use crate::types::IndicatorsParams;
use std::collections::HashMap;

/// 指标契约聚合结果（Rust 内部结构）。
#[derive(Debug, Clone, Default)]
pub struct ResolvedIndicatorContracts {
    /// source 级别的预热聚合（同 source 取最大值）。
    pub warmup_bars_by_source: HashMap<String, usize>,
    /// 指标实例契约明细，键为 `source::indicator_key`。
    pub contracts_by_indicator: HashMap<String, (String, usize, WarmupMode)>,
}

/// 聚合所有指标实例的预热契约。
pub fn resolve_indicator_contracts(
    indicators_params: &IndicatorsParams,
) -> Result<ResolvedIndicatorContracts, QuantError> {
    let registry = get_indicator_registry();
    let mut report = ResolvedIndicatorContracts::default();

    for (source, indicator_group) in indicators_params {
        for (indicator_key, raw_params) in indicator_group {
            let base_name = indicator_key.split('_').next().unwrap_or(indicator_key);
            let indicator = registry.get(base_name).ok_or_else(|| {
                QuantError::Indicator(IndicatorError::NotImplemented(format!(
                    "Indicator '{}' is not supported.",
                    base_name
                )))
            })?;

            // 统一把 Param 解析成有效数值参数，避免每个指标重复解析 optimize 规则。
            let resolved_params = raw_params
                .iter()
                .map(|(k, v)| (k.clone(), resolve_param_value(v)))
                .collect::<HashMap<_, _>>();

            let warmup_bars = indicator.required_warmup_bars(&resolved_params)?;
            let warmup_mode = indicator.warmup_mode();
            let instance_key = format!("{}::{}", source, indicator_key);

            report
                .warmup_bars_by_source
                .entry(source.clone())
                .and_modify(|x| *x = (*x).max(warmup_bars))
                .or_insert(warmup_bars);

            report.contracts_by_indicator.insert(
                instance_key,
                (source.clone(), warmup_bars, warmup_mode),
            );
        }
    }

    Ok(report)
}
