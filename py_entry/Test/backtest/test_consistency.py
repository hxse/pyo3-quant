import json

import pytest
import polars as pl
from pathlib import Path
from typing import Any

# 基准JSON文件路径
BASELINE_JSON = "baseline_result.json"


def _row_to_dict(row_df: pl.DataFrame) -> dict:
    """将Polars DataFrame的一行转换为字典"""
    if row_df.is_empty():
        return {}

    # 直接使用Polars的to_dict方法，返回第一行的数据
    row_dict = row_df.to_dict(as_series=False)

    # 提取第一行的值
    return {
        col_name: values[0]
        for col_name, values in row_dict.items()
        if values  # 确保values不为空
    }


def _save_baseline(result: dict, baseline_path: Path):
    """保存基准结果到JSON文件"""
    baseline_path.parent.mkdir(parents=True, exist_ok=True)

    # 添加元数据
    baseline_data = {
        "metadata": {
            "created_at": "2025-11-18T10:46:09Z",
            "test_file": "test_consistency.py",
            "description": "回测结果基准文件 - 防止破坏性更新",
        },
        "result": result,
    }

    with open(baseline_path, "w", encoding="utf-8") as f:
        # 使用allow_nan=False确保JSON标准兼容性
        json.dump(baseline_data, f, indent=2, ensure_ascii=False, allow_nan=False)

    print(f"📄 基准文件已保存到: {baseline_path}")


def _compare_results(current: dict, baseline: dict | None):
    """比较当前结果与基准结果 - 直接遍历字典比较"""
    # 确保baseline不为None
    if baseline is None:
        raise AssertionError("基准结果为None，无法进行比较")

    # 检查字段缺失
    missing_in_current = set(baseline.keys()) - set(current.keys())
    missing_in_baseline = set(current.keys()) - set(baseline.keys())

    if missing_in_current:
        raise AssertionError(f"当前结果缺少字段: {missing_in_current}")

    if missing_in_baseline:
        raise AssertionError(f"基准结果缺少字段: {missing_in_baseline}")

    # 直接遍历字典的 key, value 逐个比较
    differences = []
    for key, baseline_value in baseline.items():
        current_value = current.get(key)
        if not _values_equal(current_value, baseline_value):
            differences.append(
                {
                    "field": key,
                    "current": current_value,
                    "baseline": baseline_value,
                    "reason": _get_difference_reason(current_value, baseline_value),
                }
            )

    if differences:
        # 生成错误消息
        error_lines = [
            f"  {diff['field']}: 当前={diff['current']}, 基准={diff['baseline']} ({diff['reason']})"
            for diff in differences
        ]
        raise AssertionError("发现不一致的字段:\n" + "\n".join(error_lines))


def _create_diff_dict(field: str, current_val: Any, baseline_val: Any) -> dict:
    """矢量化创建差异字典"""
    return {
        "field": field,
        "current": current_val,
        "baseline": baseline_val,
        "reason": _get_difference_reason(current_val, baseline_val),
    }


def _values_equal(val1, val2) -> bool:
    """比较两个值是否相等，正确处理None和NaN"""
    # 处理None的情况
    if val1 is None and val2 is None:
        return True

    if val1 is None or val2 is None:
        return False

    # 处理NaN的情况
    val1_is_nan = isinstance(val1, float) and val1 != val1
    val2_is_nan = isinstance(val2, float) and val2 != val2

    if val1_is_nan and val2_is_nan:
        return True

    if val1_is_nan or val2_is_nan:
        return False

    # 处理数值比较
    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
        return abs(val1 - val2) <= 1e-10

    # 其他情况比较字符串
    return str(val1) == str(val2)


def _get_difference_reason(current_val, baseline_val) -> str:
    """矢量化获取差异原因"""
    return (
        "None vs value mismatch"
        if current_val is None or baseline_val is None
        else "numeric difference"
        if isinstance(current_val, (int, float))
        and isinstance(baseline_val, (int, float))
        else "string mismatch"
    )


def get_or_create_baseline(backtest_df):
    """
    工具函数：如果检测不到json，就运行一次创建json，然后返回json内容
    如果检测到json，就直接返回json内容，不覆盖
    """
    # 检查基准文件是否存在
    baseline_path = Path(__file__).parent / BASELINE_JSON

    if baseline_path.exists():
        # 如果已有JSON文件，直接加载并返回result部分，不覆盖
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline_result = json.load(f)
        return baseline_result["result"]

    # 如果没有JSON文件，创建一个新的
    # 获取最后一行的数据
    last_row = backtest_df.tail(1)

    if last_row.is_empty():
        return None

    # 将最后一行转换为字典格式
    current_result = _row_to_dict(last_row)

    # 创建基准文件
    _save_baseline(current_result, baseline_path)
    print("✅ 首次运行，已创建基准文件")

    # 返回result字段
    return current_result


class TestBacktestConsistency:
    """回测一致性测试 - 防止破坏性更新"""

    def test_result_consistency(self, backtest_df):
        """测试函数：先调用工具函数，得到json结果，然后把当前回测引擎运行结果和json里的结果做对比"""
        # 获取最后一行的数据
        last_row = backtest_df.tail(1)

        if last_row.is_empty():
            raise AssertionError("没有回测数据可比较")

        # 将最后一行转换为字典格式
        current_result = _row_to_dict(last_row)

        # 调用工具函数获取基准结果
        baseline_result = get_or_create_baseline(backtest_df)

        # 确保baseline_result不为None
        if baseline_result is None:
            raise AssertionError("基准结果为None，无法进行比较")

        # 比较结果
        _compare_results(current_result, baseline_result)

        print("✅ 一致性测试通过：结果与基准完全匹配")

    def test_update_baseline(self, backtest_df):
        """更新基准文件（当需要更新基准时使用）"""
        last_row = backtest_df.tail(1)

        if last_row.is_empty():
            raise AssertionError("没有回测数据")

        current_result = _row_to_dict(last_row)
        baseline_path = Path(__file__).parent / BASELINE_JSON

        # 检查基准文件是否已存在
        if baseline_path.exists():
            pytest.skip("基准文件已存在，不覆盖")

        # 只有在基准文件不存在时才保存新的基准文件
        _save_baseline(current_result, baseline_path)

        print("✅ 基准文件已更新")

    def test_show_current_last_row(self, backtest_df):
        """显示当前最后一行的数据（用于调试）"""
        last_row = backtest_df.tail(1)

        if last_row.is_empty():
            raise AssertionError("没有回测数据")

        # 转换为字典并美化输出
        current_result = _row_to_dict(last_row)

        # 完全矢量化显示
        if current_result:
            # 使用字典推导式矢量化创建数据
            display_data = {
                "field": list(current_result.keys()),
                "value": [
                    f"{v:.10f}" if isinstance(v, float) else str(v)
                    for v in current_result.values()
                ],
            }

            display_df = pl.DataFrame(display_data)
            print("📊 当前最后一行数据:")
            print(display_df)
        else:
            print("⚠️ 没有有效数据")
