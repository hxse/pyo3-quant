import json
import re
from pathlib import Path


def fix_notebook_cells(nb_path: Path):
    print(f"Processing {nb_path}...")
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    changed = False

    # 定义需要注入的导入语句项
    imports_to_add = "from py_entry.runner import SetupParams, FormatResultsParams, DiagnoseStatesParams\n"

    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            content = "".join(cell["source"])
            original = content

            # 1. 修复 setup()
            if ".setup(" in content and "SetupParams(" not in content:
                # 简单替换：将 .setup( 替换为 .setup(SetupParams(
                # 注意：这里需要处理字段名映射 indicators_params -> indicators 等
                content = content.replace(".setup(", ".setup(SetupParams(")
                # 映射字段名
                content = content.replace("indicators_params=", "indicators=")
                content = content.replace("signal_params=", "signal=")
                content = content.replace("backtest_params=", "backtest=")
                content = content.replace("performance_params=", "performance=")

                # 闭合括号：这比较麻烦，我们假设 setup 是链式调用中的一部分
                # 在 demo.ipynb 中通常是 .setup(...).run()
                content = re.sub(
                    r"(\.setup\(SetupParams\(.*?\))(\s*)\.run\(\)",
                    r"\1)\2.run()",
                    content,
                    flags=re.DOTALL,
                )

            # 2. 修复 format_results_for_export
            if (
                ".format_results_for_export(" in content
                and "FormatResultsParams(" not in content
            ):
                content = content.replace(
                    ".format_results_for_export(",
                    ".format_results_for_export(FormatResultsParams(",
                )
                # 假设是一行调用，补全括号
                content = re.sub(
                    r"(\.format_results_for_export\(FormatResultsParams\(.*?\))",
                    r"\1)",
                    content,
                )

            # 3. 修复 diagnose_states
            if (
                ".diagnose_states(" in content
                and "DiagnoseStatesParams(" not in content
            ):
                content = content.replace(
                    ".diagnose_states(", ".diagnose_states(DiagnoseStatesParams("
                )
                content = re.sub(
                    r"(\.diagnose_states\(DiagnoseStatesParams\(.*?\))", r"\1)", content
                )

            # 3.5 修复 enable_timing 迁移
            if "BacktestRunner(enable_timing=" in content:
                timing_match = re.search(
                    r"BacktestRunner\(enable_timing=(True|False)\)", content
                )
                if timing_match:
                    t_val = timing_match.group(1)
                    content = content.replace(timing_match.group(0), "BacktestRunner()")
                    # 注入到 SetupParams(
                    if "SetupParams(" in content:
                        content = content.replace(
                            "SetupParams(", f"SetupParams(enable_timing={t_val}, "
                        )

            # 4. 修复 display_dashboard
            if ".display_dashboard(" in content:
                # 移除旧的包装类
                content = content.replace("DisplayDashboardParams(", "")
                # 如果有嵌套的 display_config=，将其改为 config=
                content = content.replace("display_config=", "config=")
                # 处理直接使用 params= 的情况
                content = content.replace(
                    "display_dashboard(params=", "display_dashboard(config="
                )

                # 由于可能移除了包装类，可能多了一个右括号。
                # 启发式修复
                content = re.sub(
                    r"\.display_dashboard\((.*?)\)\)",
                    r".display_dashboard(\1)",
                    content,
                )

            # 5. 额外：清理导入中的残留
            if "DisplayDashboardParams" in content:
                content = content.replace(", DisplayDashboardParams", "")
                content = content.replace("DisplayDashboardParams, ", "")
                content = content.replace("DisplayDashboardParams", "")

            if content != original:
                # 注入导入语句（如果还没的话）
                if (
                    "from py_entry.runner.params" not in content
                    and "from py_entry.runner" not in content
                ):
                    content = imports_to_add + content

                # 将字符串重新拆分为列表以匹配 ipynb 格式
                cell["source"] = [line + "\n" for line in content.split("\n")]
                # 去掉最后多出来的换行符，保持格式优美
                if cell["source"][-1] == "\n":
                    cell["source"].pop()
                elif cell["source"][-1].endswith("\n"):
                    cell["source"][-1] = cell["source"][-1][:-1]

                changed = True

    if changed:
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"Fixed {nb_path}")
    else:
        print(f"No changes needed for {nb_path}")


if __name__ == "__main__":
    # 处理 Test 目录
    target_nb = Path(
        "/home/hxse/pyo3-quant/py_entry/Test/backtest/chart_reversal_extreme/demo.ipynb"
    )
    if target_nb.exists():
        fix_notebook_cells(target_nb)

    # 处理 example 目录
    example_dir = Path("/home/hxse/pyo3-quant/py_entry/example")
    for nb_file in example_dir.glob("*.ipynb"):
        fix_notebook_cells(nb_file)
