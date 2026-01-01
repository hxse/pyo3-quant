import httpx
import json

# 全局token缓存
_TOKEN_CACHE = {}


def get_local_dir(data_path, server_dir):
    """
    获取本地目录路径

    参数:
        data_path: 数据基础路径
        server_dir: 服务器目录名

    返回:
        str: 本地目录路径
    """
    return f"{data_path}/output/{server_dir}"


def get_token(token_path):
    """
    从文件中读取认证令牌

    参数:
        token_path: 令牌文件路径

    返回:
        tuple: (username, password)
    """
    with open(token_path, "r", encoding="utf-8") as file:
        data = json.load(file)
        return data["username"], data["password"]


def request_token(
    client: httpx.Client, upload_server: str, username: str | None, password: str | None
) -> str | None:
    """
    请求服务器获取访问令牌。

    参数:
    client (httpx.Client): 一个已初始化的 httpx 客户端实例。
    upload_server (str): 服务器的 URL。
    username (str): 用于认证的用户名。
    password (str): 用于认证的密码。

    返回:
    str | None: 获取到的 access_token，如果获取失败则返回 None。
    """
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "client_id": "_",
        "client_secret": "",
        "username": username,
        "password": password,
    }

    try:
        response = client.post(
            f"{upload_server}/auth/token", data=data, headers=headers
        )
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if access_token:
            _TOKEN_CACHE[(username, password)] = access_token  # 存储 token
            return access_token
        else:
            print("响应中没有找到 Access Token。")
            print("完整的响应内容：")
            print(json.dumps(token_data, indent=2))
            return None

    except httpx.HTTPStatusError as err:
        # 处理 4xx, 5xx 等 HTTP 状态码错误
        print(f"HTTP 状态错误：{err}")
        print(f"响应内容：{err.response.text}")
        return None

    except httpx.RequestError as err:
        # 捕获所有与请求/网络相关的错误，如 ConnectError, TimeoutException
        print(f"请求错误：{err}")
        # 注意：这里 err.response 可能不存在，所以不要访问它
        return None

    except Exception as e:
        # 捕获所有其他未知错误
        print(f"发生未知错误：{e}")
        return None


def get_cached_token(username: str | None, password: str | None) -> str | None:
    """
    从缓存中获取token

    参数:
        username: 用户名
        password: 密码

    返回:
        str | None: 缓存的token，如果不存在则返回None
    """
    return _TOKEN_CACHE.get((username, password))


def cache_token(username: str | None, password: str | None, token: str) -> None:
    """
    将token存储到缓存中

    参数:
        username: 用户名
        password: 密码
        token: 要缓存的token
    """
    _TOKEN_CACHE[(username, password)] = token


def clear_cached_token(username: str | None, password: str | None) -> None:
    """
    清除缓存中的token

    参数:
        username: 用户名
        password: 密码
    """
    if (username, password) in _TOKEN_CACHE:
        del _TOKEN_CACHE[(username, password)]
