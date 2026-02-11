from typing import List
from py_entry.types import SensitivityResult as RustSensitivityResult, SensitivitySample
from py_entry.io import DisplayConfig
from typing import TYPE_CHECKING, Union

# Avoid circular imports for type checking if needed, though mostly using imported types
if TYPE_CHECKING:
    from py_entry.runner.display.chart_widget import ChartDashboardWidget
    from IPython.display import HTML


class SensitivityResult:
    """敏感性测试结果包装类"""

    def __init__(self, rust_result: dict):
        self._rust_result = RustSensitivityResult.model_validate(rust_result)

    @property
    def target_metric(self) -> str:
        return self._rust_result.target_metric

    @property
    def original_value(self) -> float:
        return self._rust_result.original_value

    @property
    def mean(self) -> float:
        return self._rust_result.mean

    @property
    def std(self) -> float:
        return self._rust_result.std

    @property
    def cv(self) -> float:
        return self._rust_result.cv

    @property
    def samples(self) -> List[SensitivitySample]:
        return self._rust_result.samples

    @property
    def min(self) -> float:
        return self._rust_result.min

    @property
    def max(self) -> float:
        return self._rust_result.max

    @property
    def median(self) -> float:
        return self._rust_result.median

    def report(self):
        """打印敏感性分析报告"""
        print("\n" + "=" * 50)
        print(f"敏感性测试报告 (Target: {self.target_metric})")
        print("-" * 50)
        print(f"原始值 (Original): {self.original_value:.4f}")
        print(f"平均值 (Mean)    : {self.mean:.4f}")
        print(f"标准差 (Std)     : {self.std:.4f}")
        print(f"变异系数 (CV)    : {self.cv:.4f}")
        print(f"最小值 (Min)     : {self._rust_result.min:.4f}")
        print(f"最大值 (Max)     : {self._rust_result.max:.4f}")
        print("-" * 50)

        # 鲁棒性评价
        rating = "未知"
        if self.cv < 0.1:
            rating = "⭐⭐⭐ 非常稳健 (Very Robust)"
        elif self.cv < 0.3:
            rating = "⭐⭐ 良好 (Good)"
        elif self.cv < 0.5:
            rating = "⭐ 一般 (Average)"
        else:
            rating = "⚠️ 极度敏感 (Extremely Sensitive) - 可能过拟合"

        print(f"鲁棒性评价: {rating}")

        # Crash Rate (假设性能下降超过 50%视作崩溃)
        threshold = self.original_value * 0.5
        crashes = sum(1 for s in self.samples if s.metric_value < threshold)
        crash_rate = crashes / len(self.samples)
        print(f"崩溃率 (Crash Rate): {crash_rate:.1%} (Threshold: < {threshold:.4f})")
        print("=" * 50)

    # def display(
    #     self, config: DisplayConfig | None = None
    # ) -> Union["HTML", "ChartDashboardWidget"]:
    #     """显示图表"""
    #     pass
