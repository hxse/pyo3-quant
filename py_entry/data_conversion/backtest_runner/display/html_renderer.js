/**
 * 图表挂载逻辑模板
 * 
 * 这是一个模板文件，Python 代码会读取此文件并替换以下占位符：
 * - __CONTAINER_ID__ : 容器元素的 ID
 * - __JS_FUNCTION_NAME__ : 用于生成唯一函数名的标识符
 * - __ZIP_DATA__ : base64 编码的 ZIP 数据
 * - __CONFIG_STR__ : 转义后的配置 JSON 字符串
 * - __MOUNT_LOG__ : 日志前缀
 */

// 使用一个延迟机制，确保 DOM 元素和库加载完毕
function tryMount___JS_FUNCTION_NAME__(retryCount) {
    // 默认重试次数为 0
    if (typeof retryCount === 'undefined') retryCount = 0;
    const maxRetries = 50; // 最大重试 50 次 (约 5 秒)

    console.log("--- __MOUNT_LOG__ | 数据嵌入模式 (尝试 " + (retryCount + 1) + "/" + maxRetries + ") ---");

    const props = {
        // 从 <script type="text/plain"> 标签中读取数据，避免 JS 解析负担
        zipData: document.getElementById('__CONTAINER_ID__-data').textContent,
        // 安全地解析 JSON 字符串（已转义单引号）
        config: JSON.parse('__CONFIG_STR__')
    };

    // 检查库是否成功加载
    const libLoaded = (typeof window.ChartDashboardLib !== 'undefined' &&
        typeof window.ChartDashboardLib.mountDashboard === 'function');

    const container = document.getElementById('__CONTAINER_ID__');

    if (libLoaded && container) {
        // 执行挂载
        window.ChartDashboardLib.mountDashboard(container, props);
        console.log('✅ ChartDashboard 已成功调用 mountDashboard 进行渲染。');
    } else {
        // 如果库或容器未就绪，继续尝试，或者打印错误
        if (!container) {
            console.error('❌ 容器元素未找到：__CONTAINER_ID__。');
        } else if (!libLoaded) {
            if (retryCount < maxRetries) {
                console.warn('⚠️ 库未加载或缺少 mountDashboard 方法，将延迟 100ms 后重试...');
                setTimeout(function () { tryMount___JS_FUNCTION_NAME__(retryCount + 1); }, 100);
            } else {
                console.error('❌ 图表库加载超时。如果使用 embed_files=False，请检查网络连接或文件路径是否正确。');
                if (container) {
                    container.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100%;color:red;border:1px dashed red;padding:20px;">' +
                        '<h3>错误：图表库加载超时</h3>' +
                        '<p>可能是因为文件路径错误或网络问题导致无法加载 JavaScript 库。</p>' +
                        '</div>';
                }
            }
        }
    }
}

// 确保在所有资源加载后执行
window.onload = function () { tryMount___JS_FUNCTION_NAME__(0); };
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    tryMount___JS_FUNCTION_NAME__(0);
}
