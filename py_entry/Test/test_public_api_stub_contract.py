"""公共 PyO3 / stub 边界 smoke test。"""

from __future__ import annotations

from pathlib import Path
import re

import py_entry.types as types


def _class_block(text: str, class_name: str) -> str:
    """抽取单个 stub class 代码块。"""
    marker = f"class {class_name}:"
    if marker not in text:
        marker = f"class {class_name}(enum.Enum):"
    start = text.index(marker)
    next_class = text.find("\n@typing.final\nclass ", start + len(marker))
    if next_class == -1:
        return text[start:]
    return text[start:next_class]


def _property_names(block: str) -> set[str]:
    """提取 stub class 中的属性名集合。"""
    names: set[str] = set()
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "@property":
            continue
        for probe in lines[index + 1 :]:
            stripped = probe.strip()
            if not stripped:
                continue
            if stripped.startswith("def "):
                names.add(stripped[4:].split("(", 1)[0])
                break
    return names


def _enum_members(block: str) -> set[str]:
    """提取 stub enum 中的成员名集合。"""
    return {
        match.group(1)
        for match in re.finditer(r"^\s*([A-Z][A-Za-z0-9_]*)\s*=\s*\.\.\.$", block, re.M)
    }


def test_public_api_stub_contract() -> None:
    """公开 stitched 壳层必须只保留正式字段。"""
    stub_text = Path("python/pyo3_quant/_pyo3_quant/__init__.pyi").read_text(
        encoding="utf-8"
    )

    meta_block = _class_block(stub_text, "WindowMeta")
    assert _property_names(meta_block) == {
        "window_id",
        "best_params",
        "has_cross_boundary_position",
        "test_active_base_row_range",
        "train_warmup_time_range",
        "train_active_time_range",
        "train_pack_time_range",
        "test_warmup_time_range",
        "test_active_time_range",
        "test_pack_time_range",
    }

    window_block = _class_block(stub_text, "WindowArtifact")
    assert _property_names(window_block) == {
        "train_pack_data",
        "test_pack_data",
        "test_pack_result",
        "meta",
    }

    stitched_block = _class_block(stub_text, "StitchedArtifact")
    assert _property_names(stitched_block) == {"stitched_data", "result", "meta"}

    stitched_meta_block = _class_block(stub_text, "StitchedMeta")
    assert _property_names(stitched_meta_block) == {
        "window_count",
        "stitched_pack_time_range_from_active",
        "stitched_window_active_time_ranges",
        "backtest_schedule",
        "next_window_hint",
    }

    hint_block = _class_block(stub_text, "NextWindowHint")
    assert _property_names(hint_block) == {
        "expected_window_switch_time_ms",
        "eta_days",
        "based_on_window_id",
    }

    wf_cfg_block = _class_block(stub_text, "WalkForwardConfig")
    assert _property_names(wf_cfg_block) == {
        "train_active_bars",
        "test_active_bars",
        "min_warmup_bars",
        "warmup_mode",
        "ignore_indicator_warmup",
        "optimizer_config",
    }

    wf_mode_block = _class_block(stub_text, "WfWarmupMode")
    assert _enum_members(wf_mode_block) == {"BorrowFromTrain", "ExtendTest"}

    assert "class BacktestParamSegment:" in stub_text

    assert hasattr(types, "DataPack")
    assert hasattr(types, "ResultPack")
    assert hasattr(types, "SourceRange")
    assert hasattr(types, "BacktestParamSegment")
    assert hasattr(types, "WindowMeta")
    assert hasattr(types, "StitchedMeta")
