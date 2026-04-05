"""strategy_hub 架构守卫测试。"""

from __future__ import annotations

from pathlib import Path

from py_entry.strategy_hub.core.spec import TestStrategySpec as HubTestStrategySpec
from py_entry.strategy_hub.core.spec_loader import discover_modules
from py_entry.strategy_hub.test_strategies import get_all_strategies


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEARCH_SPACES_DIR = PROJECT_ROOT / "py_entry" / "strategy_hub" / "search_spaces"


def _search_space_folders() -> list[Path]:
    """返回搜索空间业务子目录。"""

    out: list[Path] = []
    for child in sorted(SEARCH_SPACES_DIR.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name.startswith("_"):
            continue
        if child.name in {"__pycache__", "logs", "log", "trash"}:
            continue
        out.append(child)
    return out


def test_search_spaces_root_should_not_have_strategy_files():
    """search_spaces 根目录禁止平铺策略实现文件。"""

    root_py_files = [p.name for p in SEARCH_SPACES_DIR.glob("*.py")]
    assert sorted(root_py_files) == ["__init__.py"], (
        f"search_spaces 根目录只允许 __init__.py，实际文件: {sorted(root_py_files)}"
    )


def test_each_search_space_folder_should_have_common_py():
    """每个搜索空间子目录必须包含 common.py。"""

    folders = _search_space_folders()
    assert folders, "search_spaces 下至少应有一个策略子目录"
    for folder in folders:
        common = folder / "common.py"
        assert common.exists(), f"{folder} 缺少 common.py"


def test_each_search_space_folder_should_have_strategy_entry_files():
    """每个搜索空间子目录至少应有一个可执行策略文件。"""

    folders = _search_space_folders()
    for folder in folders:
        strategy_files = [
            p.name
            for p in folder.glob("*.py")
            if p.name not in {"__init__.py", "common.py"}
        ]
        assert strategy_files, f"{folder} 没有策略入口文件"


def test_removed_arch_files_should_not_exist():
    """已删除的架构文件必须保持缺失状态。"""

    assert not (
        PROJECT_ROOT / "py_entry" / "strategy_hub" / "core" / "template.py"
    ).exists()
    assert not (PROJECT_ROOT / "py_entry" / "runner" / "pipeline.py").exists()
    assert not (
        PROJECT_ROOT / "py_entry" / "strategy_hub" / "test_strategies" / "base.py"
    ).exists()
    assert not (PROJECT_ROOT / "py_entry" / "strategies").exists()
    assert not (PROJECT_ROOT / "py_entry" / "private_strategies").exists()
    assert not (PROJECT_ROOT / "py_entry" / "example").exists()


def test_search_module_discovery_should_exclude_common_module():
    """搜索模块发现结果不应包含 common。"""

    modules = discover_modules("search")
    assert modules, "search 模块发现结果不能为空"
    assert all(not name.endswith(".common") for name in modules), modules


def test_test_strategies_should_return_spec_directly():
    """测试策略列表应直接返回 TestStrategySpec。"""

    strategies = get_all_strategies()
    assert strategies, "test_strategies 不能为空"
    assert all(isinstance(spec, HubTestStrategySpec) for spec in strategies)
