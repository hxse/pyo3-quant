from dataclasses import dataclass
from typing import Any


@dataclass
class AuthConfig:
    """认证配置"""

    username: str | None = None
    password: str | None = None
    server_url: str | None = None


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 3  # 重试次数，设为0表示不重试
    wait: int = 1
    return_on_error: Any = None  # 错误时返回的值


@dataclass
class RequestConfig:
    """请求配置，包含认证和重试配置"""

    auth: AuthConfig
    retry: RetryConfig

    @classmethod
    def create(
        cls,
        username: str | None = None,
        password: str | None = None,
        server_url: str | None = None,
        max_retries: int = 3,  # 重试次数，设为0表示不重试
        wait: int = 1,
        return_on_error: Any = None,
    ) -> "RequestConfig":
        """创建请求配置的便捷方法"""
        return cls(
            auth=AuthConfig(
                username=username, password=password, server_url=server_url
            ),
            retry=RetryConfig(
                max_retries=max_retries,
                wait=wait,
                return_on_error=return_on_error,
            ),
        )
