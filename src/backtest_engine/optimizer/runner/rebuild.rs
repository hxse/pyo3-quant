use crate::backtest_engine::optimizer::param_extractor::{set_param_value, FlattenedParam};
use crate::types::SingleParamSet;

/// 根据最优值重建参数集。
pub(super) fn rebuild_param_set(
    original: &SingleParamSet,
    flat_params: &[FlattenedParam],
    best_values: &[f64],
) -> SingleParamSet {
    let mut new_param_set = original.clone();

    for (dim, &val) in best_values.iter().enumerate() {
        if dim < flat_params.len() {
            set_param_value(&mut new_param_set, &flat_params[dim], val);
        }
    }

    new_param_set
}
