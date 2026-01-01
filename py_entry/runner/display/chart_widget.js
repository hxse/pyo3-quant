/**
 * ChartDashboardWidget - JavaScript 渲染逻辑
 *
 * 接收来自 Python 的二进制数据（DataView），转换为 base64 后传递给图表组件
 */

/**
 * 将 ArrayBuffer 转换为 base64 字符串
 */
function arrayBufferToBase64(buffer) {
    let binary = '';
    let bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}

/**
 * 动态加载 JavaScript 库
 */
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * 嵌入 JavaScript 内容
 */
function injectScript(content) {
    return new Promise((resolve, reject) => {
        try {
            // 使用 IIFE 来执行代码并挂载到 window
            // 注意：这里假设内容是 UMD 模块，它会自动挂载
            const script = document.createElement('script');
            script.textContent = `
                // 使用 IIFE (立即执行函数表达式) 来捕获和暴露 CommonJS 导出
                window.ChartDashboardLib = (function() {
                    var module = { exports: {} };
                    var exports = module.exports;
                    ${content}
                    return module.exports;
                })(window);
            `;
            document.head.appendChild(script);
            resolve();
        } catch (e) {
            reject(e);
        }
    });
}

/**
 * 动态加载 CSS 文件
 */
function loadCSS(href) {
    return new Promise((resolve, reject) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.onload = resolve;
        link.onerror = reject;
        document.head.appendChild(link);
    });
}

/**
 * 嵌入 CSS 内容
 */
function injectCSS(content) {
    const style = document.createElement('style');
    style.textContent = content;
    document.head.appendChild(style);
}

/**
 * Widget 渲染函数
 */
async function render({ model, el }) {
    console.log('🎨 [ChartDashboardWidget] 开始渲染...');

    // 获取数据和配置
    const zipDataView = model.get('zip_data');
    const config = model.get('config');
    const width = model.get('width');
    const aspectRatio = model.get('aspect_ratio');
    const libPath = model.get('lib_path');
    const cssPath = model.get('css_path');
    const embedFiles = model.get('embed_files');
    const jsContent = model.get('js_content');
    const cssContent = model.get('css_content');

    // 设置容器样式
    el.style.width = width;
    el.style.aspectRatio = aspectRatio;
    el.style.resize = 'both';
    el.style.overflow = 'hidden';

    // 添加 CSS 类以确保样式应用（特别是 min-height）
    el.classList.add("chart-dashboard-widget");

    // 转换二进制数据为 base64
    let zipBase64;
    if (zipDataView && zipDataView.buffer) {
        zipBase64 = arrayBufferToBase64(zipDataView.buffer);
        console.log('✅ [ChartDashboardWidget] 数据已转换，大小:', zipBase64.length, '字符');
    } else {
        console.error('❌ [ChartDashboardWidget] 未找到 ZIP 数据');
        el.innerHTML = '<p style="color: red;">错误：未找到图表数据</p>';
        return;
    }

    // 加载资源（嵌入或外部）
    try {
        if (embedFiles) {
            // 嵌入模式：使用 js_content 和 css_content
            if (cssContent) {
                console.log('📦 [ChartDashboardWidget] 注入嵌入的 CSS...');
                injectCSS(cssContent);
            }
            if (jsContent) {
                console.log('📦 [ChartDashboardWidget] 注入嵌入的 JS...');
                await injectScript(jsContent);
            }
        } else {
            // 外部引用模式
            console.log('📦 [ChartDashboardWidget] 加载外部资源...');
            await Promise.all([
                loadCSS(cssPath),
                loadScript(libPath)
            ]);
        }
        console.log('✅ [ChartDashboardWidget] 资源加载/注入完成');
    } catch (error) {
        console.error('❌ [ChartDashboardWidget] 资源加载失败:', error);
        el.innerHTML = `<p style="color: red;">错误：无法加载图表库 (${error.message})</p>`;
        return;
    }

    // 确保库已加载
    if (typeof window.ChartDashboardLib === 'undefined' ||
        typeof window.ChartDashboardLib.mountDashboard !== 'function') {
        console.error('❌ [ChartDashboardWidget] ChartDashboardLib 未加载');
        el.innerHTML = '<p style="color: red;">错误：图表库未正确加载，请检查 JS 文件内容。</p>';
        return;
    }

    // 挂载图表
    const props = {
        zipData: zipBase64,
        config: config
    };

    try {
        window.ChartDashboardLib.mountDashboard(el, props);
        console.log('✅ [ChartDashboardWidget] 图表挂载成功');
    } catch (error) {
        console.error('❌ [ChartDashboardWidget] 图表挂载失败:', error);
        el.innerHTML = `<p style="color: red;">错误：${error.message}</p>`;
    }
}

export default { render };
