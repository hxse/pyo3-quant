"""
HTML 渲染器 - embed_data=True 模式

生成包含 base64 编码数据的自包含 HTML
"""

import base64
import time
from typing import TYPE_CHECKING
from IPython.display import HTML
from loguru import logger

if TYPE_CHECKING:
    from ..results.run_result import RunResult

from py_entry.io import DisplayConfig
from .base import (
    generate_unique_container_id,
    escape_json_for_js,
    sanitize_id_for_js_function,
)


def render_as_html(runner: "RunResult", config: DisplayConfig) -> HTML:
    """使用 HTML 方式渲染图表仪表盘（数据嵌入模式）

    Args:
        runner: RunResult 实例
        config: DisplayConfig 配置对象

    Returns:
        HTML 对象，包含完整的图表和数据
    """
    start_time = time.perf_counter() if runner.enable_timing else None

    # 1. 获取 zip_data
    if runner.export_zip_buffer is None:
        raise ValueError(
            "未找到导出的ZIP数据。请先调用 format_results_for_export() 生成数据。"
        )
    zip_data = runner.export_zip_buffer

    # 2. 编码数据为 base64
    zip_base64 = base64.b64encode(zip_data).decode("utf-8")

    # 3. 转义配置 JSON
    config_str = escape_json_for_js(
        config.override.to_dict() if config.override else {}
    )

    # 4. 生成或使用容器 ID
    container_id = config.container_id or generate_unique_container_id()
    js_function_name = sanitize_id_for_js_function(container_id)

    # 5. 准备 JS/CSS 资源
    if config.embed_files:
        # 嵌入模式：读取文件内容
        try:
            with open(config.lib_path, "r", encoding="utf-8") as f:
                js_content = f.read()
            lib_section = f"""
            <script>
                // 使用 IIFE (立即执行函数表达式) 来捕获和暴露 CommonJS 导出
                window.ChartDashboardLib = (function() {{
                    var module = {{ exports: {{}} }};
                    var exports = module.exports;
                    {js_content}
                    return module.exports;
                }})(window);
            </script>
            """
        except FileNotFoundError:
            return HTML(
                f"<h2>错误：嵌入模式下未找到 JavaScript 库文件！请检查路径：{config.lib_path}</h2>"
            )

        try:
            with open(config.css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
            css_section = f"""
            <style>
                {css_content}
            </style>
            """
        except FileNotFoundError:
            css_section = ""
            print(f"警告：嵌入模式下未找到 CSS 文件：{config.css_path}")

        mount_log = "最终挂载尝试 (嵌入模式)"
    else:
        # 外部引用模式：使用 <script src>
        lib_section = f'<script src="{config.lib_path}"></script>'
        css_section = f'<link rel="stylesheet" href="{config.css_path}">'
        mount_log = "最终挂载尝试 (外部导入模式)"

    from pathlib import Path

    # 读取 JS 模板
    js_template_path = Path(__file__).parent / "html_renderer.js"
    try:
        with open(js_template_path, "r", encoding="utf-8") as f:
            js_template = f.read()
    except FileNotFoundError:
        # 如果找不到文件（例如打包环境），回退到内联或报错
        logger.error(f"未找到 JS 模板文件: {js_template_path}")
        return HTML(
            f"<h2>Internal Error: JS template not found at {js_template_path}</h2>"
        )

    # 替换占位符
    # 使用 replace 而不是 f-string，避免与 JS 代码中的 {} 冲突
    # 注意：__ZIP_DATA__ 已不再在 JS 中替换，而是放在 HTML 标签中
    js_code = (
        js_template.replace("__CONTAINER_ID__", container_id)
        .replace("__JS_FUNCTION_NAME__", js_function_name)
        .replace("__CONFIG_STR__", config_str)
        .replace("__MOUNT_LOG__", mount_log)
    )

    # 6. 生成 HTML 代码
    # 将数据放入 <script type="text/plain"> 中，避免 V8 引擎解析负担
    html_code = f"""
    <div id="{container_id}" style="width: {config.width}; aspect-ratio: {config.aspect_ratio}; resize: both; overflow: hidden;"></div>
    <script id="{container_id}-data" type="text/plain">{zip_base64}</script>

    {css_section}
    {lib_section}

    <script>
        {js_code}
    </script>
    """

    html_output = HTML(html_code)

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"RunResult.display() [HTML模式] 耗时: {elapsed:.4f}秒")

    return html_output
