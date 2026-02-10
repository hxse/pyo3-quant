use super::operand_resolver::{resolve_data_operand, resolve_right_operand, ResolvedOperand};
use super::types::{CompareOp, OffsetType, SignalCondition, SignalRightOperand};
use crate::error::{QuantError, SignalError};
use crate::types::DataContainer;
use crate::types::IndicatorResults;
use crate::types::SignalParams;
use polars::prelude::*;
use std::ops::{BitAnd, BitOr, Not};

/// 执行比较操作的通用函数
fn perform_comparison(
    left: &Series,
    right: &ResolvedOperand,
    right_idx: usize, // Index for right series if it's a vector
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    // 1. 执行原始比较
    let raw_result = match right {
        ResolvedOperand::Series(series_vec) => {
            let right_series = if series_vec.len() == 1 {
                &series_vec[0]
            } else {
                &series_vec[right_idx]
            };
            compare_series(left, right_series)?
        }
        ResolvedOperand::Scalar(value) => compare_scalar(left, *value)?,
    };

    // 2. 计算左操作数的无效掩码 (NaN 或 Null)
    // is_nan() 返回 True(NaN), Null(Null), False(Valid)
    // is_null() 返回 True(Null), False(Others)
    // 组合: is_nan | is_null
    // Null | True -> True (Null case covered)
    // True | False -> True (NaN case covered)
    // False | False -> False (Valid case covered)
    // 结果是没有 Null 的纯 BooleanChunked
    let left_invalid = left.is_nan()?.bitor(left.is_null());

    // 3. 计算右操作数的无效掩码并合并
    let final_mask = match right {
        ResolvedOperand::Series(series_vec) => {
            let right_series = if series_vec.len() == 1 {
                &series_vec[0]
            } else {
                &series_vec[right_idx]
            };
            let right_invalid = right_series.is_nan()?.bitor(right_series.is_null());
            left_invalid.bitor(right_invalid)
        }
        ResolvedOperand::Scalar(value) => {
            if value.is_nan() {
                // 如果标量是 NaN，所有结果都无效
                // 返回全 True 的掩码 (或者直接返回全 False 的结果)
                // 这里我们构造一个全 True 的掩码来与 left_invalid 合并 (实际上 logical OR true = true)
                // 为简单起见，后续直接处理
                let mask =
                    BooleanChunked::full(left_invalid.name().clone(), true, left_invalid.len());
                return Ok((raw_result.apply(|_| Some(false)), mask));
            }
            // 标量有效，掩码仅取决于左侧
            left_invalid
        }
    };

    // 4. 计算前导 NaN 掩码 (NaN 或 Null)
    // 注意：perform_comparison 的逻辑原本是用 !invalid 过滤 raw_result
    // 我们直接返回 final_mask 记录该位置是否有 NaN

    // 5. 过滤结果
    // result = raw_result & (!invalid)
    Ok((raw_result.bitand(final_mask.clone().not()), final_mask))
}

/// 执行简单比较（非交叉）的工具函数
fn perform_simple_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    perform_comparison(
        left_s,
        right_resolved,
        right_idx,
        compare_series,
        compare_scalar,
    )
}

/// 执行交叉比较的工具函数
///
/// 交叉比较逻辑：当前值满足条件 AND 前一个值不满足条件
fn perform_crossover_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked> + Copy,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked> + Copy,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    // 当前值的比较
    let (current, current_mask) = perform_comparison(
        left_s,
        right_resolved,
        right_idx,
        compare_series,
        compare_scalar,
    )?;

    // 前一个值的准备
    let prev_left = left_s.shift(1);
    let prev_right_resolved = match right_resolved {
        ResolvedOperand::Series(v) => {
            let s = if v.len() == 1 { &v[0] } else { &v[right_idx] };
            ResolvedOperand::Series(vec![s.shift(1)])
        }
        ResolvedOperand::Scalar(val) => ResolvedOperand::Scalar(*val),
    };

    // 前一个值的比较
    let (prev, prev_mask) = perform_comparison(
        &prev_left,
        &prev_right_resolved,
        0, // right_idx is 0 because we constructed a vec of 1
        compare_series,
        compare_scalar,
    )?;

    // 交叉信号逻辑：
    // 1. 当前值满足条件 (current)
    // 2. 前值有效 (!prev_mask) 且前值不满足条件 (prev.not())
    //
    // 如果前值有 NaN/Null (prev_mask = true)，则不触发信号
    // 这确保交叉信号仅在发生真实的状态转换时触发，而不是在数据预热期结束后立即触发
    let prev_valid_and_not_satisfied = prev.not().bitand(prev_mask.clone().not());
    let cross_result = current.bitand(prev_valid_and_not_satisfied);

    // 返回：(交叉信号, 当前掩码 OR 前值掩码)
    Ok((cross_result, current_mask.bitor(prev_mask)))
}

/// 区间穿越：矢量化预计算比较结果 + 迭代器状态机
///
/// Phase 1: 用 perform_comparison 矢量化计算 out_of_zone（SIMD 优化）
/// Phase 2: 迭代器扫描 cross + out_of_zone 的 bool 结果，维护 active 状态
fn perform_zone_cross(
    cross_result: &BooleanChunked,
    cross_mask: &BooleanChunked, // 新增：上游交叉计算的 NaN 掩码
    left_s: &Series,
    right_resolved: &ResolvedOperand, // 激活边界
    end_resolved: &ResolvedOperand,   // 终止边界 (原 upper_resolved)
    op: &CompareOp,
) -> Result<BooleanChunked, QuantError> {
    let len = left_s.len();

    // ===================== Phase 1: 矢量化预计算 =====================
    // 计算 out_of_zone = (value >= upper) | (value <= lower)
    // 逻辑：
    // - 对于 x> lower..upper:
    //   - 激活边界是 lower, 终止边界是 upper
    //   - 活跃区间是 (lower, upper)
    //   - 脱离区间 (out_of_zone): value >= upper (终止) 或 value <= lower (回落)
    // - 对于 x< upper..lower:
    //   - 激活边界是 upper, 终止边界是 lower
    //   - 活跃区间是 (lower, upper)
    //   - 脱离区间 (out_of_zone): value <= lower (终止) 或 value >= upper (回升)

    // 一次 match 确定比较方向，返回两组 (result, mask)
    let ((ooz_end, end_mask), (ooz_activate, activate_mask)) = match op {
        CompareOp::CGT => {
            // x> lower..upper: 失效条件 value >= upper(end) OR value <= lower(activate)
            (
                perform_comparison(
                    left_s,
                    end_resolved,
                    0,
                    |a, b| a.gt_eq(b),
                    |a, v| a.gt_eq(v),
                )?,
                perform_comparison(
                    left_s,
                    right_resolved,
                    0,
                    |a, b| a.lt_eq(b),
                    |a, v| a.lt_eq(v),
                )?,
            )
        }
        CompareOp::CGE => {
            // x>= lower..upper: 失效条件 value > upper(end) OR value < lower(activate)
            (
                perform_comparison(left_s, end_resolved, 0, |a, b| a.gt(b), |a, v| a.gt(v))?,
                perform_comparison(left_s, right_resolved, 0, |a, b| a.lt(b), |a, v| a.lt(v))?,
            )
        }
        CompareOp::CLT => {
            // x< upper..lower: 失效条件 value <= lower(end) OR value >= upper(activate)
            (
                perform_comparison(
                    left_s,
                    end_resolved,
                    0,
                    |a, b| a.lt_eq(b),
                    |a, v| a.lt_eq(v),
                )?,
                perform_comparison(
                    left_s,
                    right_resolved,
                    0,
                    |a, b| a.gt_eq(b),
                    |a, v| a.gt_eq(v),
                )?,
            )
        }
        CompareOp::CLE => {
            // x<= upper..lower: 失效条件 value < lower(end) OR value > upper(activate)
            (
                perform_comparison(left_s, end_resolved, 0, |a, b| a.lt(b), |a, v| a.lt(v))?,
                perform_comparison(left_s, right_resolved, 0, |a, b| a.gt(b), |a, v| a.gt(v))?,
            )
        }
        _ => {
            return Err(QuantError::Signal(SignalError::InvalidInput(format!(
                "zone_cross 仅支持交叉运算符(x>, x<, x>=, x<=)，当前运算符: {:?}",
                op
            ))));
        }
    };

    let out_of_zone = ooz_end.bitor(ooz_activate);

    // 组合无效掩码：只要 Left 或任何一侧边界是 NaN/Null，则当前 Bar 强制失效且状态重置
    // 显式合并所有来源的 NaN 掩码
    let combined_invalid = cross_mask.bitor(&end_mask).bitor(activate_mask);

    // ===================== Phase 2: 迭代器状态机 =====================
    // 输入全是预计算好的 BooleanChunked，用迭代器遍历（无边界检查开销）
    let mut result = Vec::with_capacity(len);
    let mut active = false;

    // 获取迭代器
    let cross_iter = cross_result.iter();
    let ooz_iter = out_of_zone.into_iter();
    let invalid_iter = combined_invalid.into_iter();

    for (c, (o, inv)) in cross_iter.zip(ooz_iter.zip(invalid_iter)) {
        let is_invalid = inv.unwrap_or(true);
        if is_invalid {
            active = false;
            result.push(false);
            continue;
        }

        let is_cross = c.unwrap_or(false);
        let is_ooz = o.unwrap_or(true);

        // 穿越激活（但如果同时已经 out_of_zone，则不激活）
        if is_cross && !is_ooz {
            active = true;
        } else if is_ooz {
            active = false;
        }

        result.push(active);
    }

    Ok(BooleanChunked::from_slice(
        PlSmallStr::from_static("zone_cross"),
        &result,
    ))
}

pub fn evaluate_parsed_condition(
    condition: &SignalCondition,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<(Series, BooleanChunked), QuantError> {
    let left_series_vec = resolve_data_operand(&condition.left, processed_data, indicator_dfs)?;
    let right_resolved = resolve_right_operand(
        &condition.right,
        processed_data,
        indicator_dfs,
        signal_params,
    )?;

    // Check offset type consistency
    let left_offset_type = &condition.left.offset;

    // Treat Param and Scalar as Single(0) offset for logic determination
    let binding = OffsetType::Single(0);
    let right_offset_type = match &condition.right {
        SignalRightOperand::Data(d) => &d.offset,
        _ => &binding,
    };

    // Determine logic (AND vs OR) based on OffsetType
    // If both are ranges, they must match.
    // If one is range and other is single/scalar, use the range's logic.
    // If both single, it's single (trivial AND/OR).

    let (is_and, is_or) = match (left_offset_type, right_offset_type) {
        // ==================== AND Logic ====================
        // Left is AND (Range/List), Right is AND (Range/List) or Single
        (OffsetType::RangeAnd(_, _), OffsetType::RangeAnd(_, _))
        | (OffsetType::RangeAnd(_, _), OffsetType::ListAnd(_))
        | (OffsetType::RangeAnd(_, _), OffsetType::Single(_))
        | (OffsetType::ListAnd(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::ListAnd(_), OffsetType::ListAnd(_))
        | (OffsetType::ListAnd(_), OffsetType::Single(_)) => (true, false),

        // Left is Single, Right is AND (Range/List)
        (OffsetType::Single(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::Single(_), OffsetType::ListAnd(_)) => (true, false),

        // ==================== OR Logic ====================
        // Left is OR (Range/List), Right is OR (Range/List) or Single
        (OffsetType::RangeOr(_, _), OffsetType::RangeOr(_, _))
        | (OffsetType::RangeOr(_, _), OffsetType::ListOr(_))
        | (OffsetType::RangeOr(_, _), OffsetType::Single(_))
        | (OffsetType::ListOr(_), OffsetType::RangeOr(_, _))
        | (OffsetType::ListOr(_), OffsetType::ListOr(_))
        | (OffsetType::ListOr(_), OffsetType::Single(_)) => (false, true),

        // Left is Single, Right is OR (Range/List)
        (OffsetType::Single(_), OffsetType::RangeOr(_, _))
        | (OffsetType::Single(_), OffsetType::ListOr(_)) => (false, true),

        // ==================== Single Logic ====================
        // Both are Single -> Treat as AND (trivial)
        (OffsetType::Single(_), OffsetType::Single(_)) => (true, false),

        // ==================== Invalid Combinations ====================
        _ => {
            return Err(QuantError::Signal(SignalError::InvalidOffset(format!(
                "Invalid offset combination: {:?} and {:?}",
                left_offset_type, right_offset_type
            ))));
        }
    };

    // Check lengths
    let left_len = left_series_vec.len();
    let right_len = match &right_resolved {
        ResolvedOperand::Series(v) => v.len(),
        ResolvedOperand::Scalar(_) => 1,
    };

    // 使用 match 清晰地处理4种广播情况
    let comparison_pairs: Vec<(usize, usize)> = match (left_len, right_len) {
        // 情况1：左右都是1，直接比较
        (1, 1) => vec![(0, 0)],

        // 情况2：左边>1，右边是1，左边每个元素都与右边比较
        (l, 1) if l > 1 => (0..l).map(|i| (i, 0)).collect(),

        // 情况3：左边是1，右边>1，左边与右边每个元素比较
        (1, r) if r > 1 => (0..r).map(|i| (0, i)).collect(),

        // 情况4：左右长度相等且>1，逐对比较
        (l, r) if l == r && l > 1 => (0..l).map(|i| (i, i)).collect(),

        // 其他情况：长度不匹配，报错
        (l, r) => {
            return Err(QuantError::Signal(SignalError::InvalidOffset(format!(
                "操作数长度不匹配，无法进行广播。\n\
                 左操作数长度: {}\n\
                 右操作数长度: {}\n\
                 左操作数: {:?}\n\
                 右操作数: {:?}\n\
                 提示：广播规则为：(1,1), (n,1), (1,n), (n,n)，其中 n>1",
                l, r, condition.left, condition.right
            ))));
        }
    };

    let mut final_result: Option<BooleanChunked> = None;
    let mut final_mask: Option<BooleanChunked> = None;

    for (left_idx, right_idx) in comparison_pairs {
        let left_s = &left_series_vec[left_idx];

        let (comparison_result, mask_result) = match condition.op {
            CompareOp::GT => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt(b),
                |a, v| a.gt(v),
            )?,
            CompareOp::LT => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt(b),
                |a, v| a.lt(v),
            )?,
            CompareOp::GE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
            CompareOp::LE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
            CompareOp::EQ => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.equal(b),
                |a, v| a.equal(v),
            )?,
            CompareOp::NE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?,
            CompareOp::CGT => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt(b),
                |a, v| a.gt(v),
            )?,
            CompareOp::CLT => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt(b),
                |a, v| a.lt(v),
            )?,
            CompareOp::CGE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
            CompareOp::CLE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
            CompareOp::CEQ => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.equal(b),
                |a, v| a.equal(v),
            )?,
            CompareOp::CNE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?,
        };

        match final_result {
            None => final_result = Some(comparison_result),
            Some(ref mut res) => {
                if is_and {
                    *res = res.clone().bitand(comparison_result.clone());
                } else if is_or {
                    *res = res.clone().bitor(comparison_result.clone());
                }
            }
        }

        match final_mask {
            None => final_mask = Some(mask_result),
            Some(ref mut m) => {
                // 对于 NaN 掩码，无论是 AND 还是 OR 逻辑，我们都倾向于追踪任何一个 NaN。
                // 这样用户知道这组计算中只要有一个 NaN。
                *m = m.clone().bitor(mask_result);
            }
        }
    }

    let mut result_series = final_result
        .ok_or_else(|| {
            QuantError::Signal(SignalError::InvalidInput(
                "Empty comparison result".to_string(),
            ))
        })?
        .into_series()
        .fill_null(FillNullStrategy::Zero)?;

    let mut mask = final_mask.ok_or_else(|| {
        QuantError::Signal(SignalError::InvalidInput("Empty mask result".to_string()))
    })?;

    // 区间穿越 (Zone Cross) 处理
    if let Some(zone_end_operand) = &condition.zone_end {
        let end_resolved = resolve_right_operand(
            zone_end_operand,
            processed_data,
            indicator_dfs,
            signal_params,
        )?;

        // 先合并 end_resolved 的 NaN mask（在 zone cross 计算之前）
        if let ResolvedOperand::Series(end_series_vec) = &end_resolved {
            let end_s = &end_series_vec[0];
            let end_invalid = end_s.is_nan()?.bitor(end_s.is_null());
            mask = mask.bitor(end_invalid);
        }

        // result_series 此时是普通 cross 的瞬时结果
        let cross_bool = result_series.bool()?.clone();
        // Zone Cross 只支持单值偏移，且在之前的约束校验中已保证
        let left_s = &left_series_vec[0];

        let zone_result = perform_zone_cross(
            &cross_bool,
            &mask,
            left_s,
            &right_resolved,
            &end_resolved,
            &condition.op,
        )?;

        result_series = zone_result.into_series();
    }

    if condition.negated {
        let bool_chunked = result_series
            .bool()
            .map_err(|_| {
                QuantError::Signal(SignalError::InvalidInput(
                    "Result is not boolean".to_string(),
                ))
            })?
            .clone();
        result_series = bool_chunked.not().into_series();
    }

    Ok((result_series, mask))
}
