use crate::backtest_engine::indicators::adx::{adx_eager, ADXConfig};
use crate::backtest_engine::indicators::atr::atr_eager;
use crate::backtest_engine::indicators::bbands::bbands_eager;
use crate::backtest_engine::indicators::ema::ema_eager;
use crate::backtest_engine::indicators::macd::macd_eager;
use crate::backtest_engine::indicators::psar::psar_eager;
use crate::backtest_engine::indicators::rma::rma_eager;
use crate::backtest_engine::indicators::rsi::rsi_eager;
use crate::backtest_engine::indicators::sma::sma_eager;
use crate::backtest_engine::indicators::tr::tr_eager;
use crate::data_conversion::input::param::Param;
use polars::prelude::*;
use pyo3::{
    exceptions::{PyKeyError, PyRuntimeError},
    PyResult,
};
use std::collections::HashMap;

/// 计算单个周期的指标
pub fn calculate_single_period_indicators(
    ohlcv_df: &DataFrame,
    period_params: &HashMap<String, HashMap<String, Param>>,
) -> PyResult<DataFrame> {
    // 指定泛型参数避免类型推断失败，初始化为空列 DataFrame
    let mut indicators_df = ohlcv_df
        .select::<Vec<&str>, &str>(vec![])
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for (indicator_key, param_map) in period_params {
        if indicator_key.starts_with("sma_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64; // 将 f64 转换为 i64
            let sma_series =
                sma_eager(ohlcv_df, period).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            // 使用 with_name 返回新 Series，并转换字符串类型
            let named_sma = sma_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_sma)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("bbands_") {
            // 提取length和std参数
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let std_param = param_map.get("std").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'std' not found for indicator '{}'",
                    indicator_key
                ))
            })?;

            let period = period_param.value as i64;
            let std = std_param.value; // f64类型,不需要转换

            // 调用calculate_bbands
            let (lower, middle, upper, bandwidth, percent) = bbands_eager(ohlcv_df, period, std)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            // 添加5个Series到indicators_df,使用正确的列名
            let lower_named = lower.with_name(format!("{}_lower", indicator_key).as_str().into());
            let middle_named =
                middle.with_name(format!("{}_middle", indicator_key).as_str().into());
            let upper_named = upper.with_name(format!("{}_upper", indicator_key).as_str().into());
            let bandwidth_named =
                bandwidth.with_name(format!("{}_bandwidth", indicator_key).as_str().into());
            let percent_named =
                percent.with_name(format!("{}_percent", indicator_key).as_str().into());

            indicators_df
                .with_column(lower_named)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(middle_named)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(upper_named)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(bandwidth_named)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(percent_named)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("ema_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64;
            let ema_series =
                ema_eager(ohlcv_df, period).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let named_ema = ema_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_ema)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("tr_") {
            let tr_series =
                tr_eager(ohlcv_df).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let named_tr = tr_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_tr)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("rma_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64;
            let rma_series =
                rma_eager(ohlcv_df, period).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let named_rma = rma_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_rma)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("atr_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64;
            let atr_series =
                atr_eager(ohlcv_df, period).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let named_atr = atr_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_atr)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("rsi_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64;
            let rsi_series =
                rsi_eager(ohlcv_df, period).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            let named_atr = rsi_series.with_name(indicator_key.as_str().into());
            indicators_df
                .with_column(named_atr)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("psar_") {
            let af0_param = param_map.get("af0").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'af0' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let af_step_param = param_map.get("af_step").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'af_step' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let max_af_param = param_map.get("max_af").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'max_af' not found for indicator '{}'",
                    indicator_key
                ))
            })?;

            let af0 = af0_param.value;
            let af_step = af_step_param.value;
            let max_af = max_af_param.value;

            let (psar_long, psar_short, psar_af, psar_reversal) =
                psar_eager(ohlcv_df, af0, af_step, max_af)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(psar_long.with_name(format!("{}_long", indicator_key).as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(
                    psar_short.with_name(format!("{}_short", indicator_key).as_str().into()),
                )
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(psar_af.with_name(format!("{}_af", indicator_key).as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(
                    psar_reversal.with_name(format!("{}_reversal", indicator_key).as_str().into()),
                )
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("macd_") {
            let fast_period_param = param_map.get("fast_period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'fast_period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let slow_period_param = param_map.get("slow_period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'slow_period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let signal_period_param = param_map.get("signal_period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'signal_period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;

            let fast_period = fast_period_param.value as i64;
            let slow_period = slow_period_param.value as i64;
            let signal_period = signal_period_param.value as i64;

            let macd_alias_str = format!("{}_macd", indicator_key);
            let signal_alias_str = format!("{}_signal", indicator_key);
            let hist_alias_str = format!("{}_hist", indicator_key);

            let (macd_series, signal_series, hist_series) = macd_eager(
                ohlcv_df,
                "close", // MACD通常基于close价格计算
                fast_period,
                slow_period,
                signal_period,
                macd_alias_str.as_str(),
                signal_alias_str.as_str(),
                hist_alias_str.as_str(),
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(macd_series)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(signal_series)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            indicators_df
                .with_column(hist_series)
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        } else if indicator_key.starts_with("adx_") {
            let period_param = param_map.get("period").ok_or_else(|| {
                PyKeyError::new_err(format!(
                    "Parameter 'period' not found for indicator '{}'",
                    indicator_key
                ))
            })?;
            let period = period_param.value as i64;
            let adxr_length = param_map
                .get("adxr_length")
                .map(|p| p.value as i64)
                .unwrap_or(2); // 默认值为 2

            let adx_alias_str = format!("{}_adx", indicator_key);
            let plus_dm_alias_str = format!("{}_plus_dm", indicator_key);
            let minus_dm_alias_str = format!("{}_minus_dm", indicator_key);
            let adxr_alias_str = format!("{}_adxr", indicator_key);

            let (adx_series, adxr_series, plus_dm_series, minus_dm_series) = adx_eager(
                ohlcv_df,
                &ADXConfig {
                    high_col: "high".to_string(),
                    low_col: "low".to_string(),
                    close_col: "close".to_string(),
                    period,
                    adx_alias: adx_alias_str.clone(),
                    plus_dm_alias: plus_dm_alias_str.clone(),
                    minus_dm_alias: minus_dm_alias_str.clone(),
                    adxr_length,
                    adxr_alias: adxr_alias_str.clone(),
                },
            )
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

            indicators_df
                .with_column(adx_series.with_name(adx_alias_str.as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
                .with_column(adxr_series.with_name(adxr_alias_str.as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
                .with_column(plus_dm_series.with_name(plus_dm_alias_str.as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?
                .with_column(minus_dm_series.with_name(minus_dm_alias_str.as_str().into()))
                .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        }
    }
    Ok(indicators_df)
}
