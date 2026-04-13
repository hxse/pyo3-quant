"""公开面旧名字护栏测试。"""

from __future__ import annotations

from pathlib import Path


# 中文注释：这里只扫描正式公开面，避免把 task 文档或历史记录误判为回流。
PUBLIC_SURFACE_FILES = (
    Path("py_entry/runner/__init__.py"),
    Path("py_entry/io/__init__.py"),
    Path("python/pyo3_quant/_pyo3_quant/__init__.pyi"),
    Path("python/pyo3_quant/backtest_engine/__init__.pyi"),
)

# 中文注释：这些名字都属于本次 breaking 收口后不应再出现在公开面的旧口径。
LEGACY_PUBLIC_NAMES = (
    "RunResult",
    "BatchResult",
    "WalkForwardResultWrapper",
    "OptimizeResult",
    "SensitivityResultWrapper",
    "OptunaOptResult",
    "format_for_export",
    "format_results_for_export",
    "run_backtest_engine",
    "py_run_backtest_engine",
    "validate_wf_indicator_readiness",
    "execution_stage",
    "return_only_final",
)


def test_public_surface_blocks_legacy_names() -> None:
    """正式公开面不应重新暴露旧名字或旧入口。"""
    unexpected_hits: list[str] = []
    for path in PUBLIC_SURFACE_FILES:
        text = path.read_text(encoding="utf-8")
        for legacy_name in LEGACY_PUBLIC_NAMES:
            if legacy_name in text:
                unexpected_hits.append(f"{path}: {legacy_name}")

    assert unexpected_hits == [], "\n".join(unexpected_hits)
