import io
import time
from pathlib import Path
from py_entry.data_conversion.file_utils.common import make_authenticated_request
from py_entry.data_conversion.file_utils.types import RequestConfig


def upload_data(
    config: RequestConfig,
    files: dict,
) -> None:
    """
    将文件上传到服务器，并处理 401 错误重试逻辑。

    参数:
    files (dict): 包含要上传文件的字典。
    config: 请求配置，包含认证和重试参数。

    返回:
    None: 函数不返回任何值。
    """

    def upload_request(client, headers):
        response = client.post(
            f"{config.auth.server_url}/file/upload", files=files, headers=headers
        )
        response.raise_for_status()
        return None  # 上传成功，返回None

    make_authenticated_request(
        config=config,
        request_func=upload_request,
        error_context="上传文件到服务器",
    )


def upload_to_server(
    config: RequestConfig,
    zip_data: bytes,
    server_dir: Path | None = None,
    zip_name: str = "strategy.zip",
):
    """
    将 ZIP 文件的字节数据上传到指定的服务器。

    参数:
    zip_data (bytes): ZIP 文件的字节数据。
    config: 请求配置，包含认证和重试参数。
    server_dir (Path | None): ZIP 文件所在的目录路径，用于生成默认文件名。
    zip_name (str): ZIP 文件的名称，默认为 "strategy.zip"。
    """
    start_time = time.perf_counter()

    file_path = (
        Path(server_dir) if server_dir else Path("./")
    ) / f"{zip_name if zip_name else 'temp.zip'}"

    zip_file_to_upload = io.BytesIO(zip_data)
    files = {
        "file": (
            file_path.as_posix(),
            zip_file_to_upload,
            "application/zip",
        )
    }

    upload_data(config, files)
    # 假设如果函数执行到这里没有抛出异常，则表示上传尝试完成
    # 具体的成功/失败信息会在 upload_data 内部打印
    time_elapsed = time.perf_counter() - start_time
    print(f"ZIP 文件上传用时 {time_elapsed:.2f} 秒")
