import zipfile
import io
from pathlib import Path
from typing import List, Tuple
import zlib


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
    # 注意：zipfile 库本身不支持直接设置压缩级别
    # 但你可以通过手动调用 zlib 来实现

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zipf:
        for path, buffer in data_list:
            buffer.seek(0)
            data = buffer.getvalue()

            # 手动压缩数据
            compressed_data = zlib.compress(data, compress_level)

            # 创建 ZipInfo 对象并设置压缩信息
            info = zipfile.ZipInfo(str(path))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.compress_size = len(compressed_data)
            info.file_size = len(data)

            # 将预先压缩好的数据写入 ZIP
            zipf.writestr(info, compressed_data)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
