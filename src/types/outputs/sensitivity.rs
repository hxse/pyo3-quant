use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// 单个样本的测试结果
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct SensitivitySample {
    /// 采样后的参数值
    pub values: Vec<f64>,
    /// 目标指标值
    pub metric_value: f64,
    /// 所有性能指标
    pub all_metrics: HashMap<String, f64>,
}

/// 敏感性测试总结果
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct SensitivityResult {
    pub target_metric: String,
    pub original_value: f64,
    pub samples: Vec<SensitivitySample>,

    // 统计量
    pub mean: f64,
    pub std: f64,
    pub min: f64,
    pub max: f64,
    pub median: f64,
    pub cv: f64, // 变异系数 (std / mean)
}

#[gen_stub_pymethods]
#[pymethods]
impl SensitivityResult {
    /// 生成敏感性分析报告文本
    #[pyo3(text_signature = "($self)")]
    pub fn report(&self) -> String {
        // 鲁棒性评价
        let rating = if self.cv < 0.1 {
            "Very Robust"
        } else if self.cv < 0.3 {
            "Good"
        } else if self.cv < 0.5 {
            "Average"
        } else {
            "Extremely Sensitive - 可能过拟合"
        };

        // Crash Rate (假设性能下降超过 50%视作崩溃)
        let threshold = self.original_value * 0.5;
        let crashes = self
            .samples
            .iter()
            .filter(|s| s.metric_value < threshold)
            .count();
        let crash_rate = crashes as f64 / self.samples.len() as f64;

        // 统一返回字符串，由 Python 决定打印方式，便于 notebook/pytest 捕获。
        let mut lines = Vec::with_capacity(13);
        lines.push(String::new());
        lines.push("=".repeat(50));
        lines.push(format!("敏感性测试报告 (Target: {})", self.target_metric));
        lines.push("-".repeat(50));
        lines.push(format!("原始值 (Original): {:.4}", self.original_value));
        lines.push(format!("平均值 (Mean)    : {:.4}", self.mean));
        lines.push(format!("标准差 (Std)     : {:.4}", self.std));
        lines.push(format!("变异系数 (CV)    : {:.4}", self.cv));
        lines.push(format!("最小值 (Min)     : {:.4}", self.min));
        lines.push(format!("最大值 (Max)     : {:.4}", self.max));
        lines.push("-".repeat(50));
        lines.push(format!("鲁棒性评价: {}", rating));
        lines.push(format!(
            "崩溃率 (Crash Rate): {:.1}% (Threshold: < {:.4})",
            crash_rate * 100.0,
            threshold
        ));
        lines.push("=".repeat(50));
        lines.join("\n")
    }
}
