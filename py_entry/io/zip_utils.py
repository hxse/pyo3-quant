import zipfile
import io
from pathlib import Path
from typing import List, Tuple


def create_zip_buffer(
    data_list: List[Tuple[Path, io.BytesIO]], compress_level: int = 1
) -> bytes:
    """
    将内存中的文件打包成 ZIP, 并返回 ZIP 压缩包的字节数据
    可以指定压缩级别来调整速度
    如果文件大部分是csv格式, 建议用1
    如果文件大部分是parquet格式, 建议用0

    参数:
        data_list: 包含(路径, 字节流)元组的列表
        compress_level: 压缩级别, 0-9, 数字越大压缩率越高但速度越慢

    返回:
        bytes: ZIP压缩包的字节数据
    """
    zip_buffer = io.BytesIO()

    # 使用正确的压缩级别创建 ZIP 文件
    with zipfile.ZipFile(
        zip_buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=compress_level
    ) as zipf:
        for path, buffer in data_list:
            buffer.seek(0)
            data = buffer.getvalue()

            # 直接写入原始数据，让 zipfile 自动处理压缩
            zipf.writestr(str(path), data)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
