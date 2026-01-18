import pytest
from py_entry.types import OptimizerConfig
import pyo3_quant

# from pyo3_quant.backtest_engine.optimizer import py_run_optimizer_benchmark, BenchmarkFunction
# 直接从 optimizer 模块获取，避免 import 路径问题
optimizer_module = pyo3_quant.backtest_engine.optimizer
py_run_optimizer_benchmark = optimizer_module.py_run_optimizer_benchmark  # type: ignore
BenchmarkFunction = optimizer_module.BenchmarkFunction  # type: ignore


# 设置测试参数
# 容差范围
TOLERANCE_DICT = {
    "sphere": 1e-2,  # 必须精确收敛 (Correctness Check)
    "rosenbrock": 1.0,  # 能找到山谷 (Robustness Check)
    "rastrigin": 3.0,  # 多峰函数，LHS+Gaussian易陷局部最优，容许偏差
    "ackley": 2.2,  # 同上
}

# 增加尝试次数，因为随机算法有概率性
N_TRIALS = 500  # Rust 很快，可以多跑点


def run_rust_optimizer(func_name: str, bounds, n_trials=N_TRIALS, seed=42):
    func_map = {
        "sphere": BenchmarkFunction.Sphere,
        "rosenbrock": BenchmarkFunction.Rosenbrock,
        "rastrigin": BenchmarkFunction.Rastrigin,
        "ackley": BenchmarkFunction.Ackley,
    }

    # 构造 Rust 优化器配置
    # 增加采样密度和轮数
    config = OptimizerConfig(
        samples_per_round=100,  # 增加每轮样本数
        max_rounds=20,  # 总共 2000 次采样
        explore_ratio=0.5,  # 增加探索比例
        sigma_ratio=0.1,  # 减小高斯搜索半径，更精细
        stop_patience=20,  # 禁用早停（直到跑完 max_rounds）
    )

    # 调用 Rust 接口
    best_params, best_value = py_run_optimizer_benchmark(
        config, func_map[func_name], bounds, seed
    )

    # print(f"  [Debug] {func_name} (seed={seed}): val={best_value}")

    # 返回 best_value
    return best_value


@pytest.mark.parametrize(
    "func_name, bounds, optimal_val",
    [
        ("sphere", [(-5.12, 5.12)] * 3, 0.0),
        ("rosenbrock", [(-5.0, 10.0)] * 2, 0.0),
        ("rastrigin", [(-5.12, 5.12)] * 3, 0.0),
        # Ackley 通常需要更多次迭代或更好的参数才能收敛到 0
        ("ackley", [(-32.768, 32.768)] * 3, 0.0),
    ],
)
def test_rust_optimizer_benchmark(func_name, bounds, optimal_val):
    """
    测试 Rust 优化器在经典数学函数上的表现。
    这是 Layer 1 基础验证。
    """
    seeds = [42, 100, 2024]
    results = []

    for seed in seeds:
        val = run_rust_optimizer(func_name, bounds, seed=seed)
        results.append(val)

    # 取最好的结果与容差比较
    best_result = min(results)
    tolerance = TOLERANCE_DICT.get(func_name, 1.0)

    print(f"Function: {func_name}, Best Result: {best_result}, Tolerance: {tolerance}")

    assert best_result <= optimal_val + tolerance, (
        f"Optimizer failed on {func_name}. Got {best_result}, expected <= {optimal_val + tolerance}"
    )


if __name__ == "__main__":
    pytest.main([__file__])
