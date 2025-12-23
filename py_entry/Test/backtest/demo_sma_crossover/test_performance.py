"""
performance.json 验证测试

验证逻辑：
- JSON 不存在 → 报错，提示需要先在 demo.ipynb 中人工可视化审阅并生成
- 结果不一致 → 报错，提示可能有破坏性更新，需人工审阅
"""

import pytest
import json
from pathlib import Path


def test_performance_matches_baseline(backtest_result):
    """验证回测性能指标与 JSON 基准一致"""
    demo_dir = Path(__file__).parent
    json_path = demo_dir / "performance.json"

    # 1. 检查 JSON 是否存在
    if not json_path.exists():
        pytest.fail(
            f"❌ 基准文件不存在: {json_path}\n\n"
            "请先手动运行 demo.ipynb：\n"
            "1. 在 Jupyter 中执行所有 cell\n"
            "2. 在可视化仪表板中人工审阅回测结果\n"
            "3. 确认无误后，执行最后一个 cell 生成 performance.json\n"
        )

    # 2. 加载基准数据
    with open(json_path) as f:
        baseline = json.load(f)

    # 3. 获取当前结果
    current = backtest_result[0].performance

    # 4. 逐项比较
    mismatches = []
    # 比较所有基准中存在的指标
    for key in baseline:
        if key not in current:
            mismatches.append(f"缺少指标: {key}")
        else:
            b_val = baseline[key]
            c_val = current[key]

            if isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
                # 数值类型使用容差比较
                if abs(c_val - b_val) > 1e-10:
                    mismatches.append(
                        f"{key}: 当前={c_val}, 基准={b_val} (差异={c_val - b_val})"
                    )
            elif c_val != b_val:
                # 其他类型直接比较
                mismatches.append(f"{key}: 当前={c_val}, 基准={b_val}")

    if mismatches:
        pytest.fail(
            "⚠️ 检测到潜在的破坏性更新！\n\n"
            "回测结果与 performance.json 基准不一致：\n"
            + "\n".join(f"  - {m}" for m in mismatches)
            + "\n\n如果这是预期的变更，请：\n"
            "1. 运行 demo.ipynb 在可视化仪表板中审阅变更\n"
            "2. 确认变更合理后，重新生成 performance.json\n"
            "3. 提交新的基准文件"
        )
