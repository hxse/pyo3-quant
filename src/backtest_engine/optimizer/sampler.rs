use rand::distr::Distribution;
use rand::seq::SliceRandom;
use rand::Rng;
use rand_distr::Normal;

/// Latin Hypercube Sampling (自实现)
/// 返回 n_samples × n_dims 的采样矩阵，值在 [0, 1] 范围
pub fn lhs_sample(n_samples: usize, n_dims: usize, rng: &mut impl Rng) -> Vec<Vec<f64>> {
    if n_samples == 0 || n_dims == 0 {
        return vec![];
    }

    let columns: Vec<Vec<f64>> = (0..n_dims)
        .map(|_| {
            let mut col: Vec<f64> = (0..n_samples)
                .map(|i| {
                    let lower = i as f64 / n_samples as f64;
                    let upper = (i + 1) as f64 / n_samples as f64;
                    rng.random_range(lower..upper)
                })
                .collect();
            col.shuffle(rng);
            col
        })
        .collect();

    let mut result = Vec::with_capacity(n_samples);
    for i in 0..n_samples {
        let row: Vec<f64> = columns.iter().map(|c| c[i]).collect();
        result.push(row);
    }
    result
}

/// 将 [0, 1] 采样值变换到参数空间
pub fn transform_sample(u: f64, min: f64, max: f64, log_scale: bool) -> f64 {
    if log_scale {
        // 防止 log(0)
        let safe_min = if min <= 0.0 { 1e-6 } else { min };
        let safe_max = if max <= 0.0 { 1e-6 } else { max };
        let log_min = safe_min.ln();
        let log_max = safe_max.ln();
        (log_min + u * (log_max - log_min)).exp()
    } else {
        min + u * (max - min)
    }
}

/// 基于多个高斯分量的加权采样
/// weighted_centers: (value, weight) 的集合
/// sigma_ratio: 搜索范围的百分比
pub fn weighted_gaussian_sample(
    weighted_centers: &[(f64, f64)],
    min: f64,
    max: f64,
    sigma_ratio: f64,
    log_scale: bool,
    rng: &mut impl Rng,
) -> f64 {
    if weighted_centers.is_empty() {
        return rng.random_range(min..max);
    }

    // 处理对数空间
    let (s_min, s_max, s_centers) = if log_scale {
        let l_min = min.max(1e-6).ln();
        let l_max = max.max(1e-6).ln();
        let l_centers: Vec<(f64, f64)> = weighted_centers
            .iter()
            .map(|(v, w)| (v.max(1e-6).ln(), *w))
            .collect();
        (l_min, l_max, l_centers)
    } else {
        (min, max, weighted_centers.to_vec())
    };

    let sigma = (s_max - s_min) * sigma_ratio;

    // 按权重随机选一个中心
    let total_weight: f64 = s_centers.iter().map(|(_, w)| *w).sum();
    let mut r = rng.random_range(0.0..total_weight);
    let mut selected_center = s_centers[0].0;
    for (val, w) in s_centers {
        if r < w {
            selected_center = val;
            break;
        }
        r -= w;
    }

    // 正态分布采样
    let normal =
        Normal::new(selected_center, sigma).unwrap_or(Normal::new(selected_center, 0.01).unwrap());
    let mut sample_raw = normal.sample(rng);

    // 裁剪到边界
    sample_raw = sample_raw.clamp(s_min, s_max);

    if log_scale {
        sample_raw.exp()
    } else {
        sample_raw
    }
}
