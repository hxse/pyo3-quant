import json
from pathlib import Path
from py_entry.io import RequestConfig


def load_local_config(config_name: str = "config.json") -> RequestConfig:
    """
    加载本地配置文件。

    查找顺序：
    1. ./data/{config_name} (相对于当前工作目录)
    2. {project_root}/data/{config_name} (相对于项目根目录)

    Args:
        config_name: 配置文件名，默认为 "config.json"

    Returns:
        RequestConfig: 请求配置对象

    Raises:
        FileNotFoundError: 如果找不到配置文件
    """
    # 1. 尝试相对于当前工作目录
    config_path = Path(f"data/{config_name}")

    if not config_path.exists():
        # 尝试推断项目根目录
        # 本文件在 py_entry/io/config_loader.py
        # root 在 py_entry 的上一级
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        config_path = project_root / "data" / config_name

    if not config_path.exists():
        # 再试一下 py_entry/example/data/config.json (为了兼容旧的 example 路径)
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "py_entry/example/data" / config_name

    if not config_path.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {config_path} (查找路径包括 CWD 和 Project Root)"
        )

    with open(config_path, "r") as f:
        json_config = json.load(f)

    return RequestConfig.create(
        username=json_config["username"],
        password=json_config["password"],
        server_url=json_config["server_url"],
    )
