// src/backtest_engine/indicators/registry.rs
use super::adx::AdxIndicator;
use super::atr::AtrIndicator;
use super::bbands::BbandsIndicator;
use super::cci::CciIndicator;
use super::ema::EmaIndicator;
use super::er::ErIndicator;
use super::extended::divergence::{
    CciDivergenceIndicator, MacdDivergenceIndicator, RsiDivergenceIndicator,
};
use super::extended::session::OpeningBarIndicator;
use super::extended::sma_close_pct::SmaClosePctIndicator;
use super::macd::MacdIndicator;
use super::psar::PsarIndicator;
use super::rma::RmaIndicator;
use super::rsi::RsiIndicator;
use super::sma::SmaIndicator;
use super::tr::TrIndicator;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;
use std::sync::OnceLock;

/// 指标预热校验模式。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WarmupMode {
    Strict,
    Relaxed,
}

/// 所有指标必须实现的通用 Trait
pub trait Indicator: Send + Sync {
    /// 统一的计算接口
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError>;

    /// 返回该指标所需的最小预热 K 线数量。
    fn required_warmup_bars(&self, resolved_params: &HashMap<String, f64>)
        -> Result<usize, QuantError>;

    /// 返回该指标的运行时校验模式。
    /// 中文注释：强约束要求每个指标必须显式声明，禁止依赖默认实现。
    fn warmup_mode(&self) -> WarmupMode;
}

/// 指标注册表类型别名
pub type IndicatorRegistry = HashMap<String, Box<dyn Indicator>>;

/// 使用 OnceLock 创建全局唯一的指标注册表
static REGISTRY: OnceLock<IndicatorRegistry> = OnceLock::new();

/// 获取指标注册表的单例
pub fn get_indicator_registry() -> &'static IndicatorRegistry {
    REGISTRY.get_or_init(|| {
        let mut registry: IndicatorRegistry = HashMap::new();
        registry.insert("sma".to_string(), Box::new(SmaIndicator));
        registry.insert("bbands".to_string(), Box::new(BbandsIndicator));
        registry.insert("psar".to_string(), Box::new(PsarIndicator));
        registry.insert("adx".to_string(), Box::new(AdxIndicator));
        registry.insert("atr".to_string(), Box::new(AtrIndicator));
        registry.insert("ema".to_string(), Box::new(EmaIndicator));
        registry.insert("macd".to_string(), Box::new(MacdIndicator));
        registry.insert("rma".to_string(), Box::new(RmaIndicator));
        registry.insert("rsi".to_string(), Box::new(RsiIndicator));
        registry.insert("tr".to_string(), Box::new(TrIndicator));
        registry.insert("cci".to_string(), Box::new(CciIndicator));
        registry.insert("er".to_string(), Box::new(ErIndicator));
        registry.insert(
            "cci-divergence".to_string(),
            Box::new(CciDivergenceIndicator),
        );
        registry.insert(
            "rsi-divergence".to_string(),
            Box::new(RsiDivergenceIndicator),
        );
        registry.insert(
            "macd-divergence".to_string(),
            Box::new(MacdDivergenceIndicator),
        );
        registry.insert("opening-bar".to_string(), Box::new(OpeningBarIndicator));
        registry.insert("sma-close-pct".to_string(), Box::new(SmaClosePctIndicator));
        registry
    })
}

/// 统一参数解析规则：`optimize=true` 取 `max`，否则取 `value`。
pub fn resolve_param_value(param: &Param) -> f64 {
    if param.optimize { param.max } else { param.value }
}

/// 读取必填参数（缺失时直接报错）。
pub fn require_resolved_param(
    params: &HashMap<String, f64>,
    key: &str,
    indicator_name: &str,
) -> Result<f64, QuantError> {
    params.get(key).copied().ok_or_else(|| {
        QuantError::Indicator(IndicatorError::InvalidParameter(
            indicator_name.to_string(),
            format!("Missing required parameter '{}'", key),
        ))
    })
}
