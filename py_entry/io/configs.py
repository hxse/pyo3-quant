from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, model_validator
from .types import RequestConfig
from py_entry.types import DashboardOverride

ParquetCompression = Literal[
    "lz4", "uncompressed", "snappy", "gzip", "lzo", "brotli", "zstd"
]
default_parquet_compression = "snappy"


def _find_project_root() -> Optional[Path]:
    """查找项目根目录（包含 pyproject.toml 的目录）

    Returns:
        项目根目录的绝对路径，如果找不到则返回 None
    """
    # 从当前文件位置开始向上查找
    current_file = Path(__file__).resolve()

    # 检查当前文件的父目录
    for parent in [current_file] + list(current_file.parents):
        if (parent / "pyproject.toml").is_file():
            return parent

    # 如果从文件路径找不到，尝试从当前工作目录查找
    current_dir = Path.cwd()
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "pyproject.toml").is_file():
            return parent

    return None


class SaveConfig(BaseModel):
    """保存结果的配置"""

    output_dir: str | Path  # 相对于 data/output 的路径


class UploadConfig(BaseModel):
    """上传结果的配置"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_config: RequestConfig
    server_dir: str | None = None
    zip_name: str | None = None


class DisplayConfig(BaseModel):
    """显示仪表盘的配置

    推荐配置组合：
    - embed_data=False, embed_files=True: Jupyter 环境最佳（默认）
    - embed_data=True, embed_files=True: 导出自包含 HTML
    - target="marimo": Marimo 环境（强制 anywidget 模式，自动 mo.ui.anywidget 包装）

    路径说明：
    - lib_path 和 css_path 支持相对路径和绝对路径
    - 相对路径会自动转换为基于项目根目录的绝对路径
    - 这样可以确保在 VS Code Jupyter 和浏览器 Jupyter 中行为一致
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 目标环境
    # "jupyter": 默认，支持 anywidget 和 HTML 内嵌两种模式
    # "marimo": 强制使用 anywidget 模式，并用 mo.ui.anywidget() 包装（忽略 embed_data）
    target: Literal["jupyter", "marimo"] = "jupyter"

    # 仪表盘覆盖配置
    override: Optional[DashboardOverride] = None

    # UMD JavaScript 库文件的路径
    # 默认使用相对路径，会在 __post_init__ 中自动转换为绝对路径
    lib_path: str = "data/lwchart/chart-dashboard.umd.js"

    # CSS 文件的路径
    # 默认使用相对路径，会在 __post_init__ 中自动转换为绝对路径
    css_path: str = "data/lwchart/lwchart_demo3.css"

    # 是否将 JS/CSS 文件内容嵌入
    # True: 自包含，无需外部文件（推荐，稳定可靠）
    # False: 从 lib_path/css_path 加载外部文件（需要配置下载权限，可能不稳定）
    embed_files: bool = True

    # 是否将数据编码到 HTML 中
    # True: 数据作为 base64 硬编码到 HTML（适合导出自包含 HTML）
    # False: 通过 anywidget 传递二进制数据（仅 Jupyter 环境，性能更好）
    embed_data: bool = False

    # 用于渲染图表的 HTML 容器 ID（可选）
    container_id: Optional[str] = None

    # 图表容器的宽度，例如 "100%" 或 "800px"
    width: str = "100%"

    # 图表容器的宽高比，例如 "16/9" 或 "4/3"
    aspect_ratio: str = "16/9"

    @model_validator(mode="after")
    def _post_init(self) -> "DisplayConfig":
        """初始化后处理：将相对路径转换为绝对路径，并设置默认 override"""
        # 设置默认的 override 配置
        if self.override is None:
            self.override = DashboardOverride(showRiskLegend="1,1,1,1")

        # 查找项目根目录
        project_root = _find_project_root()

        if project_root:
            # 处理 lib_path
            lib_path_obj = Path(self.lib_path)
            if not lib_path_obj.is_absolute():
                self.lib_path = str(project_root / self.lib_path)

            # 处理 css_path
            css_path_obj = Path(self.css_path)
            if not css_path_obj.is_absolute():
                self.css_path = str(project_root / self.css_path)
        # 如果找不到项目根目录，保持原路径不变（可能用户提供了绝对路径或相对路径）

        return self
