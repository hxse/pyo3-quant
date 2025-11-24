// src/backtest_engine/indicators/registry.rs
use super::adx::AdxIndicator;
use super::atr::AtrIndicator;
use super::bbands::BbandsIndicator;
use super::ema::EmaIndicator;
use super::extended::sma_close_pct::SmaClosePctIndicator;
use super::macd::MacdIndicator;
use super::psar::PsarIndicator;
use super::rma::RmaIndicator;
use super::rsi::RsiIndicator;
use super::sma::SmaIndicator;
use super::tr::TrIndicator;
use crate::data_conversion::types::param::Param;
use crate::error::QuantError;
use polars::prelude::*;
use std::collections::HashMap;
use std::sync::OnceLock;

/// 所有指标必须实现的通用 Trait
pub trait Indicator: Send + Sync {
    /// 统一的计算接口
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError>;
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
        registry.insert("sma-close-pct".to_string(), Box::new(SmaClosePctIndicator));
        registry
    })
}
