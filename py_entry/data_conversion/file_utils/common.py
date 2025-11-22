import httpx
import time
from typing import Any, Callable
from py_entry.data_conversion.file_utils.auth import (
    request_token,
    get_cached_token,
    clear_cached_token,
)
from py_entry.data_conversion.file_utils.types import RequestConfig

# 全局HTTP客户端
_global_client: httpx.Client | None = None


def get_global_client() -> httpx.Client:
    """获取全局HTTP客户端，如果不存在则创建一个新的"""
    global _global_client
    if _global_client is None:
        _global_client = httpx.Client()
    return _global_client


def close_global_client():
    """关闭全局HTTP客户端"""
    global _global_client
    if _global_client is not None:
        _global_client.close()
        _global_client = None


def make_authenticated_request(
    config: RequestConfig,
    request_func: Callable[[httpx.Client, dict[str, str]], Any],
    error_context: str,
) -> Any:
    """
    通用的认证HTTP请求处理函数，包含重试逻辑和token管理。

    参数:
    request_func: 执行HTTP请求的函数，接收client和headers参数
    error_context (str): 错误信息上下文，用于打印错误信息
    config: 请求配置，包含认证和重试参数

    返回:
    Any: 请求成功时返回请求结果，失败时返回 return_on_error 值。
    """
    client = get_global_client()
    retries = config.retry.max_retries
    while retries >= 0:
        # 从缓存获取 token 或请求新 token 的逻辑
        access_token = get_cached_token(config.auth.username, config.auth.password)
        if (
            not access_token
            and config.auth.username
            and config.auth.password
            and config.auth.server_url
        ):
            access_token = request_token(
                client,
                config.auth.server_url,
                config.auth.username,
                config.auth.password,
            )
            if not access_token:
                print(f"无法获取 Access Token，{error_context}中止。")
                return config.retry.return_on_error

        try:
            headers: dict[str, str] = {}
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"

            # 执行传入的请求函数
            result = request_func(client, headers)
            return result

        except httpx.HTTPStatusError as e:
            if (
                e.response.status_code == 401
                and config.auth.username
                and config.auth.password
            ):
                print(
                    f"{error_context}失败: HTTP 状态码 401 (Unauthorized)。尝试重新获取 Access Token 并重试。"
                )
                clear_cached_token(
                    config.auth.username, config.auth.password
                )  # 清空缓存中的 token
            else:
                print(f"{error_context}失败: HTTP 状态码错误 - {e}")

        except (httpx.HTTPError, httpx.RequestError) as e:
            print(f"{error_context}失败: 请求或HTTP错误 - {e}")
        except Exception as e:
            print(f"{error_context}失败: 未知错误 - {e}")
            return config.retry.return_on_error  # 遇到未知错误，直接退出

        if retries > 0:
            print(f"剩余重试次数: {retries}")
            retries -= 1
            time.sleep(config.retry.wait)  # 等待一秒后重试
        else:
            print(f"重试次数已用尽，{error_context}中止。")
            return config.retry.return_on_error  # 重试次数用尽，退出函数
