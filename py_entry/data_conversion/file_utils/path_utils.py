"""路径和文件系统相关的工具函数"""

import shutil
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录。

    通过查找 pyproject.toml 来确定项目根目录。

    Returns:
        项目根目录路径

    Raises:
        RuntimeError: 如果找不到项目根目录
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("无法找到项目根目录（没有 pyproject.toml）")


def validate_output_path(output_dir: str | Path) -> Path:
    """验证输出路径是否在允许的范围内。

    输出路径必须在项目根目录的 data/output 文件夹下。

    Args:
        output_dir: 要验证的输出目录

    Returns:
        验证后的绝对路径

    Raises:
        ValueError: 如果路径不在允许的范围内
    """
    project_root = get_project_root()
    allowed_base = project_root / "data" / "output"

    # 转换为 Path 对象
    output_path = Path(output_dir)

    # 如果是相对路径，则相对于 allowed_base
    if not output_path.is_absolute():
        output_path = allowed_base / output_path

    # 解析为绝对路径
    output_path = output_path.resolve()
    allowed_base = allowed_base.resolve()

    # 检查是否在允许的基础目录下
    if not output_path.is_relative_to(allowed_base):
        raise ValueError(
            f"输出目录必须在 {allowed_base} 下面。\n"
            f"当前路径: {output_path}\n"
            f"允许的基础路径: {allowed_base}"
        )

    return output_path


def clear_directory(directory: Path, keep_dir: bool = True) -> None:
    """清空目录内容。

    Args:
        directory: 要清空的目录
        keep_dir: 是否保留目录本身（只删除内容）
    """
    if not directory.exists():
        return

    if keep_dir:
        # 删除目录内容但保留目录
        for item in directory.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        # 删除整个目录
        shutil.rmtree(directory)
