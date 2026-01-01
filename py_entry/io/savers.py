"""将buffer保存到磁盘的工具函数"""

import io
from pathlib import Path
from typing import List, Tuple


def save_buffers_to_disk(
    buffer_list: List[Tuple[Path, io.BytesIO]],
    output_dir: Path,
) -> Path:
    """将buffer列表保存到磁盘。

    Args:
        buffer_list: 包含(相对路径, BytesIO)元组的列表
        output_dir: 输出目录（已验证的绝对路径）

    Returns:
        实际保存的目录路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在保存结果到: {output_dir}")

    for rel_path, buffer in buffer_list:
        file_path = output_dir / rel_path
        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        buffer.seek(0)
        with open(file_path, "wb") as f:
            f.write(buffer.read())

    print(f"保存完成，共 {len(buffer_list)} 个文件")
    return output_dir
