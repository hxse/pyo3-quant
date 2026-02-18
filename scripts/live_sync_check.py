from pathlib import Path
import sys
import hashlib


def file_sha256(path: Path) -> str:
    """计算文件内容 SHA-256，用于跨环境稳定比对。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    """检查 private research/live 同名策略文件是否一致。"""
    project_root = Path(__file__).resolve().parents[1]
    live_dir = project_root / "py_entry/private_strategies/live"
    research_dir = project_root / "py_entry/private_strategies/research"

    # research 默认是私有目录，新 clone 缺失时跳过属于预期行为。
    if not research_dir.exists():
        print("live-sync-check: skip (research 目录不存在，符合默认私有管理模式)")
        return 0

    skip_names = {"__init__.py", "base.py"}
    mismatches: list[tuple[str, str, str]] = []
    missing_pairs: list[str] = []
    checked = 0

    for live_file in sorted(live_dir.glob("*.py"), key=lambda p: p.name):
        if live_file.name in skip_names or live_file.name.startswith("_"):
            continue

        research_file = research_dir / live_file.name
        if not research_file.exists():
            missing_pairs.append(str(research_file))
            continue

        checked += 1
        live_hash = file_sha256(live_file)
        research_hash = file_sha256(research_file)
        if live_hash != research_hash:
            mismatches.append((live_file.name, live_hash, research_hash))

    if missing_pairs:
        print("live-sync-check: fail (live 同名 research 文件缺失)")
        for path in missing_pairs:
            print(f"  - {path}")
        return 1

    if mismatches:
        print("live-sync-check: fail (research/live 同名策略文件不一致)")
        for name, live_hash, research_hash in mismatches:
            print(f"  - {name}")
            print(f"    live:     {live_hash}")
            print(f"    research: {research_hash}")
        return 1

    print(f"live-sync-check: ok (checked={checked})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
