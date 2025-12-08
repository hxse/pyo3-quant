import base64
import json
import random
import time
from IPython.display import HTML, display
from typing import Dict, Any, Optional
from pathlib import Path
import os


# 导入 BacktestRunner 的类型提示
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_entry.data_conversion.backtest_runner.runner import BacktestRunner


def display_dashboard(
    self: "BacktestRunner",
    config: Dict[str, Any],
    dataframe_format: str,
    compress_level: int,
    lib_path: str,
    css_path: str,
    embed_files: bool,
    container_id: Optional[str],
) -> HTML:
    """
    获取回测结果的 ZIP 压缩包字节数据，并将其加载到 ChartDashboard 组件中。

    Args:
        self: BacktestRunner 实例。
        config (dict): ChartDashboard 的配置字典。
        dataframe_format: DataFrame格式，"csv" 或 "parquet"。
        compress_level: 压缩级别，0-9。
        lib_path (str): UMD JavaScript 库文件的路径。
        css_path (str): CSS 文件的路径。
        embed_files (bool):
            - True: 将 JS/CSS 文件内容读取并嵌入到 HTML 中（自包含）。
            - False: 使用 <script src> 和 <link> 外部引用文件。
        container_id (str):
            - 可选参数。用于渲染图表的 HTML 容器 ID。
            - 默认为 None。如果未提供，将自动生成一个基于时间的唯一 ID。

    Returns:
        HTML: IPython.display.HTML 对象，用于在 Jupyter 中渲染图表。
    """
    # 1. 获取 zip_data (委托给 result_logic 中的 get_zip_buffer)
    zip_data = self.get_zip_buffer(
        dataframe_format=dataframe_format, compress_level=compress_level
    )

    # --- 1. 数据准备 ---
    # 编码数据
    zip_base64 = base64.b64encode(zip_data).decode("utf-8")
    # 将 Python 字典转换为标准的 JS JSON 字符串
    config_str = json.dumps(config)

    # --- 2. 唯一 ID 处理 ---
    # 如果用户没有提供 ID，则生成一个唯一 ID
    if container_id is None:
        # 使用当前时间（毫秒级）
        unique_timestamp = int(time.time() * 1000)

        # 使用随机数（0到99999）
        random_part = random.randint(0, 99999)

        # 组合：时间戳 + 随机数，使其更具随机性
        container_id = f"chart-dashboard-container-{unique_timestamp}-{random_part}"

    # 使用提供的或生成的 ID
    final_container_id = container_id

    # --- 3. 模式切换：外部引用 (False) vs. 嵌入 (True) ---
    if embed_files:
        # 嵌入模式：读取文件内容
        # 尝试读取 JS 文件
        try:
            # 假设 lib_path 是相对于当前工作目录的路径
            with open(lib_path, "r", encoding="utf-8") as f:
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
                f"<h2>错误：嵌入模式下未找到 JavaScript 库文件！请检查路径：{lib_path}</h2>"
            )

        # 尝试读取 CSS 文件
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
            css_section = f"""
            <style>
                {css_content}
            </style>
            """
        except FileNotFoundError:
            css_section = ""
            # 保持用户提供的逻辑，但使用 print
            print(f"警告：嵌入模式下未找到 CSS 文件：{css_path}")

        mount_log = "最终挂载尝试 (嵌入模式)"

    else:
        # 外部引用模式：使用 <script src>
        lib_section = f'<script src="{lib_path}"></script>'
        css_section = f'<link rel="stylesheet" href="{css_path}">'
        mount_log = "最终挂载尝试 (外部导入模式)"

    # --- 4. 创建 HTML/JS 结构 ---
    html_code = f"""
    <div id="{final_container_id}" style="height: 600px; width: 100%;"></div>

    {css_section}
    {lib_section}

    <script>
        // 使用一个延迟机制，确保 DOM 元素和库加载完毕
        function tryMount() {{
            console.log("--- {mount_log} ---");

            const props = {{
                zipData: "{zip_base64}",
                // 安全地解析 JSON 字符串
                config: JSON.parse('{config_str}')
            }};

            // 检查库是否成功加载 (假设 UMD 库将其导出对象挂载到了 window.ChartDashboardLib)
            const libLoaded = (typeof window.ChartDashboardLib !== 'undefined' &&
                                typeof window.ChartDashboardLib.mountDashboard === 'function');

            const container = document.getElementById('{final_container_id}');

            if (libLoaded && container) {{
                // 执行挂载
                window.ChartDashboardLib.mountDashboard(container, props);
                console.log('✅ ChartDashboard 已成功调用 mountDashboard 进行渲染。');
            }} else {{
                // 如果库或容器未就绪，继续尝试，或者打印错误
                if (!container) {{
                    console.error('❌ 容器元素未找到：{final_container_id}。');
                }} else if (!libLoaded) {{
                    console.warn('⚠️ 库未加载或缺少 mountDashboard 方法，将延迟 100ms 后重试...');
                    // 在外部引用模式下，可能需要短暂延迟以等待文件加载完成
                    setTimeout(tryMount, 100);
                }}
            }}
        }}

        // 在外部引用模式下，使用 setTimeout 确保在 <script src> 后的代码能正常运行
        // 在嵌入模式下，IIFE 已经执行，可以立即尝试挂载
        window.onload = tryMount; // 确保在所有资源加载后执行，更安全
        if (document.readyState === 'complete' || document.readyState === 'interactive') {{
            // 如果页面已经加载完毕，则立即尝试
            tryMount();
        }}
    </script>
    """
    # ⚠️ 注意：在 f-string 中，< 和 > 必须转义，否则会被 HTML 解析器错误处理
    # 已经将 <script> 和 <link> 等标签中的 < 和 > 替换为 < 和 >
    return HTML(html_code)
