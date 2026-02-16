"""
ChartDashboardWidget - 使用 anywidget 实现的图表仪表盘组件

通过 Jupyter Widgets 协议进行二进制数据传输，无需 base64 编码。
"""

import anywidget
import traitlets
from typing import Dict, Any
from pathlib import Path

_ASSET_DIR = Path(__file__).parent
# 直接内嵌 ESM/CSS 字符串，避免 marimo 在动态加载 @file 模块时偶发 404。
_ESM_SOURCE = (_ASSET_DIR / "chart_widget.js").read_text(encoding="utf-8")
_CSS_SOURCE = (_ASSET_DIR / "chart_widget.css").read_text(encoding="utf-8")


class ChartDashboardWidget(anywidget.AnyWidget):
    """图表仪表盘 Widget

    使用 anywidget 实现，支持高效的二进制数据传输。
    数据通过 traitlets.Bytes 传输，无需 base64 编码，性能优于传统方式约 33%。
    """

    # 二进制 ZIP 数据（自动在 Python 和 JavaScript 之间传输）
    zip_data = traitlets.Bytes().tag(sync=True)

    # 仪表盘配置
    config = traitlets.Dict(default_value={}).tag(sync=True)

    # 容器样式配置
    # 目标环境：jupyter / marimo
    target = traitlets.Unicode(default_value="jupyter").tag(sync=True)
    width = traitlets.Unicode(default_value="100%").tag(sync=True)
    aspect_ratio = traitlets.Unicode(default_value="16/9").tag(sync=True)

    # 库和样式路径
    lib_path = traitlets.Unicode(default_value="../lwchart/chart-dashboard.umd.js").tag(
        sync=True
    )
    css_path = traitlets.Unicode(default_value="../lwchart/lwchart_demo3.css").tag(
        sync=True
    )
    embed_files = traitlets.Bool(default_value=True).tag(sync=True)

    # 嵌入的文件内容
    js_content = traitlets.Unicode(default_value="").tag(sync=True)
    css_content = traitlets.Unicode(default_value="").tag(sync=True)

    # JavaScript 模块（ESM）
    _esm = _ESM_SOURCE

    # CSS 样式
    _css = _CSS_SOURCE

    def __init__(
        self,
        *,
        zip_data: bytes,
        config: Dict[str, Any],
        target: str = "jupyter",
        width: str = "100%",
        aspect_ratio: str = "16/9",
        lib_path: str = "",
        css_path: str = "",
        embed_files: bool = True,
        js_content: str = "",
        css_content: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            zip_data=zip_data,
            config=config,
            target=target,
            width=width,
            aspect_ratio=aspect_ratio,
            lib_path=lib_path,
            css_path=css_path,
            embed_files=embed_files,
            js_content=js_content,
            css_content=css_content,
            **kwargs,
        )
