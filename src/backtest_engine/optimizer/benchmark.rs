use crate::types::BenchmarkFunction;
use pyo3::prelude::*;
use std::f64::consts::PI;

impl BenchmarkFunction {
    pub fn evaluate(&self, x: &[f64]) -> f64 {
        match self {
            Self::Sphere => x.iter().map(|v| v * v).sum(),
            Self::Rosenbrock => {
                if x.is_empty() {
                    return 0.0;
                }
                (0..x.len() - 1)
                    .map(|i| 100.0 * (x[i + 1] - x[i].powi(2)).powi(2) + (1.0 - x[i]).powi(2))
                    .sum()
            }
            Self::Rastrigin => {
                let a = 10.0;
                let n = x.len() as f64;
                a * n
                    + x.iter()
                        .map(|v| v.powi(2) - a * (2.0 * PI * v).cos())
                        .sum::<f64>()
            }
            Self::Ackley => {
                let a = 20.0;
                let b = 0.2;
                let c = 2.0 * PI;
                let n = x.len() as f64;

                if n == 0.0 {
                    return 0.0;
                }

                let sum1: f64 = x.iter().map(|v| v.powi(2)).sum();
                let sum2: f64 = x.iter().map(|v| (c * v).cos()).sum();
                -a * (-b * (sum1 / n).sqrt()).exp() - (sum2 / n).exp() + a + std::f64::consts::E
            }
        }
    }
}
