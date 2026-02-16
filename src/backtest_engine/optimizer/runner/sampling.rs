use crate::backtest_engine::optimizer::param_extractor::{quantize_value, FlattenedParam};
use crate::backtest_engine::optimizer::sampler::{
    lhs_sample, transform_sample, weighted_gaussian_sample,
};
use crate::types::{OptimizerConfig, SamplePoint};
use rand::rngs::StdRng;

/// 生成一批采样点的参数值。
pub(super) fn generate_samples(
    n_samples: usize,
    explore_count: usize,
    n_dims: usize,
    flat_params: &[FlattenedParam],
    top_k_samples: &[SamplePoint],
    config: &OptimizerConfig,
    rng: &mut StdRng,
    current_round: usize,
) -> Vec<Vec<f64>> {
    let exploitation_count = n_samples - explore_count;
    let mut next_round_vals = Vec::with_capacity(n_samples);

    // Sigma Decay: 轮数增加时减小采样半径
    let decay = 1.0 / (current_round as f64).sqrt();
    let current_sigma_ratio = config.sigma_ratio * decay;

    // 探索部分：LHS
    if explore_count > 0 {
        let u_samples = lhs_sample(explore_count, n_dims, rng);
        for u_row in u_samples {
            let mut vals = Vec::new();
            for (dim, &u) in u_row.iter().enumerate() {
                let p = &flat_params[dim];
                let val = transform_sample(u, p.param.min, p.param.max, p.param.log_scale);
                vals.push(quantize_value(val, p.param.step, p.param.dtype));
            }
            next_round_vals.push(vals);
        }
    }

    // 利用部分：加权高斯
    if exploitation_count > 0 && !top_k_samples.is_empty() {
        for _ in 0..exploitation_count {
            let mut vals = Vec::new();
            for (dim, p) in flat_params.iter().enumerate() {
                let centers: Vec<(f64, f64)> = top_k_samples
                    .iter()
                    .enumerate()
                    .map(|(i, s)| {
                        let weight = (-(config.weight_decay * i as f64)).exp();
                        (s.values[dim], weight)
                    })
                    .collect();

                let val = weighted_gaussian_sample(
                    &centers,
                    p.param.min,
                    p.param.max,
                    current_sigma_ratio,
                    p.param.log_scale,
                    rng,
                );
                vals.push(quantize_value(val, p.param.step, p.param.dtype));
            }
            next_round_vals.push(vals);
        }
    }

    next_round_vals
}
