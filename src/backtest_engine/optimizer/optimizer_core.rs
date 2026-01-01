//! 优化器核心逻辑模块
//!
//! 包含优化状态管理、停止条件检测、TopK维护等核心功能

use crate::types::RoundSummary;

/// 采样点结构
#[derive(Clone, Debug)]
pub struct SamplePoint {
    /// 各维度的参数值
    pub values: Vec<f64>,
    /// 该参数组合的 Calmar 比率
    pub calmar: f64,
}

/// 优化器配置验证结果
pub struct ValidationResult {
    pub is_valid: bool,
    pub errors: Vec<String>,
}

/// 验证优化器配置的合法性
///
/// # 参数
/// * `explore_ratio` - 探索比例
/// * `top_k_ratio` - TopK 比例
/// * `samples_per_round` - 每轮采样数
/// * `sigma_ratio` - 高斯核标准差比例
///
/// # 返回
/// 验证结果
pub fn validate_config(
    explore_ratio: f64,
    top_k_ratio: f64,
    samples_per_round: usize,
    sigma_ratio: f64,
) -> ValidationResult {
    let mut errors = Vec::new();

    if !(0.0..=1.0).contains(&explore_ratio) {
        errors.push(format!(
            "explore_ratio must be in [0, 1], got {}",
            explore_ratio
        ));
    }

    if !(0.0..=1.0).contains(&top_k_ratio) {
        errors.push(format!(
            "top_k_ratio must be in [0, 1], got {}",
            top_k_ratio
        ));
    }

    if samples_per_round == 0 {
        errors.push("samples_per_round must be > 0".to_string());
    }

    if sigma_ratio <= 0.0 {
        errors.push(format!("sigma_ratio must be > 0, got {}", sigma_ratio));
    }

    ValidationResult {
        is_valid: errors.is_empty(),
        errors,
    }
}

/// 检查是否应该因长时间无改善而停止
///
/// 由于 history 存储的是累积最佳值，如果连续 patience 轮该值没有变化，则认为已收敛。
///
/// # 参数
/// * `history` - 历史轮次摘要（包含累积最佳值）
/// * `patience` - 耐心轮数（连续多少轮无新高则停止）
///
/// # 返回
/// 是否应该停止
pub fn should_stop_patience(history: &[RoundSummary], patience: usize) -> bool {
    // 轮数基础检查
    if history.len() <= patience {
        return false;
    }

    // 获取当前（最后一轮）的累积最佳
    let current_best = history.last().unwrap().best_calmar;

    // 获取 patience 轮之前的累积最佳
    let prev_idx = history.len() - 1 - patience;
    let prev_best = history[prev_idx].best_calmar;

    // 如果 current_best <= prev_best，说明这 patience 轮里没有任何一轮创新高
    current_best <= prev_best
}

/// 合并并更新 TopK 样本
///
/// # 参数
/// * `existing_top_k` - 现有的 TopK 样本
/// * `new_samples` - 新的采样结果（需要已排序）
/// * `k` - 保留的数量
///
/// # 返回
/// 更新后的 TopK 样本
pub fn merge_top_k(
    existing_top_k: &[SamplePoint],
    new_samples: &[SamplePoint],
    k: usize,
) -> Vec<SamplePoint> {
    let mut combined: Vec<SamplePoint> = existing_top_k.iter().cloned().collect();
    combined.extend(new_samples.iter().cloned());

    // 按 Calmar 降序排序
    combined.sort_by(|a, b| {
        b.calmar
            .partial_cmp(&a.calmar)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // 取前 k 个
    combined.truncate(k);
    combined
}
