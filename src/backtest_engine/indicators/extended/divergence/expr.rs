use super::config::DivergenceConfig;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 核心背离计算逻辑（单次循环计算双向背离）
/// 返回 Struct 列，包含 `top` 和 `bottom`。
pub fn divergence_expr(config: &DivergenceConfig) -> Result<Expr, QuantError> {
    let indicator_col = config.indicator_col.clone();
    let window = config.window;
    let gap_threshold = config.gap;
    let recency_threshold = config.recency;

    let div_expr = col(&indicator_col).map_many(
        move |s| {
            let indicator = s[0]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let high = s[1]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let low = s[2]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let len = indicator.len();

            let mut top_results = Vec::with_capacity(len);
            let mut bot_results = Vec::with_capacity(len);

            for _ in 0..(window - 1) {
                top_results.push(false);
                bot_results.push(false);
            }

            for i in (window - 1)..len {
                let start_idx = i + 1 - window;
                let end_idx = i;

                let mut max_p = f64::MIN;
                let mut max_p_idx = 0;
                let mut min_p = f64::MAX;
                let mut min_p_idx = 0;

                let mut max_i = f64::MIN;
                let mut max_i_idx = 0;
                let mut min_i = f64::MAX;
                let mut min_i_idx = 0;

                let mut has_nan = false;

                for j in start_idx..=end_idx {
                    let h = high.get(j).unwrap_or(f64::NAN);
                    let l = low.get(j).unwrap_or(f64::NAN);
                    let ind = indicator.get(j).unwrap_or(f64::NAN);

                    if h.is_nan() || l.is_nan() || ind.is_nan() {
                        has_nan = true;
                        break;
                    }

                    if h >= max_p {
                        max_p = h;
                        max_p_idx = j;
                    }
                    if ind >= max_i {
                        max_i = ind;
                        max_i_idx = j;
                    }

                    if l <= min_p {
                        min_p = l;
                        min_p_idx = j;
                    }
                    if ind <= min_i {
                        min_i = ind;
                        min_i_idx = j;
                    }
                }

                if has_nan {
                    top_results.push(false);
                    bot_results.push(false);
                    continue;
                }

                let top_recency_ok = (end_idx - max_p_idx) < recency_threshold as usize;
                let top_gap = max_p_idx as i32 - max_i_idx as i32;
                let top_ok =
                    top_recency_ok && (max_p_idx > max_i_idx) && (top_gap >= gap_threshold);

                let bot_recency_ok = (end_idx - min_p_idx) < recency_threshold as usize;
                let bot_gap = min_p_idx as i32 - min_i_idx as i32;
                let bot_ok =
                    bot_recency_ok && (min_p_idx > min_i_idx) && (bot_gap >= gap_threshold);

                top_results.push(top_ok);
                bot_results.push(bot_ok);
            }

            let s_top = Series::new("top".into(), top_results);
            let s_bot = Series::new("bottom".into(), bot_results);

            let df_div = df![
                "top" => s_top,
                "bottom" => s_bot
            ]
            .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;

            let s_struct = df_div.into_struct("divergence".into()).into_series();
            Ok(s_struct.into_column())
        },
        &[col("high"), col("low")],
        move |_, _| {
            let fields = vec![
                Field::new("top".into(), DataType::Boolean),
                Field::new("bottom".into(), DataType::Boolean),
            ];
            Ok(Field::new("divergence".into(), DataType::Struct(fields)))
        },
    );

    Ok(div_expr)
}
