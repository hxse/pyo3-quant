from typing import Any, List, TYPE_CHECKING

from py_entry.types import ResultPack, SingleParamSet
from py_entry.runner.results.report_json import dump_report

if TYPE_CHECKING:
    from .run_result import RunResult
    # Context types if needed


class BatchResult:
    """批量回测结果"""

    def __init__(
        self,
        results: List[ResultPack],
        param_list: List[SingleParamSet],
        context: dict,  # data_pack, template_config, engine_settings
    ):
        self.results = results
        self.param_list = param_list
        self.context = context

    def select(self, index: int = 0) -> "RunResult":
        """选择一个结果转为 RunResult"""
        from .run_result import RunResult

        if index < 0 or index >= len(self.results):
            raise IndexError(f"Index {index} out of range (0-{len(self.results) - 1})")

        return RunResult(
            result=self.results[index],
            params=self.param_list[index],
            data_pack=self.context["data_pack"],
            template_config=self.context["template_config"],
            engine_settings=self.context["engine_settings"],
            enable_timing=self.context.get("enable_timing", False),
        )

    def best_by(self, metric: str = "calmar_ratio") -> "RunResult":
        """按指标选择最优结果"""
        # Simple implementation
        if not self.results:
            raise ValueError("No results in batch")

        best_idx = max(
            range(len(self.results)),
            key=lambda i: float(
                (self.results[i].performance or {}).get(metric, -float("inf"))
            ),
        )

        return self.select(best_idx)

    def build_report(self) -> dict[str, Any]:
        """构建批量回测统一报告。"""
        rows: list[dict[str, Any]] = []
        for idx, result in enumerate(self.results):
            rows.append(
                {
                    "index": idx,
                    "performance": result.performance or {},
                }
            )
        return {
            "stage": "batch",
            "total_results": len(self.results),
            "results": rows,
        }

    def print_report(self) -> None:
        """打印批量回测统一报告。"""
        print(dump_report(self.build_report()))
