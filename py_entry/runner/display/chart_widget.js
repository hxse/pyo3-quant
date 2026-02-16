// ChartDashboardWidget 渲染（精简版，保留最小稳定修复）

function bytesToBase64(bytes) {
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i += 1) {
        binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
}

function normalizeToBytes(value) {
    if (!value) return null;
    if (value instanceof ArrayBuffer) return new Uint8Array(value);
    if (ArrayBuffer.isView(value)) return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    if (value.buffer instanceof ArrayBuffer && typeof value.byteLength === 'number') {
        return new Uint8Array(value.buffer, value.byteOffset || 0, value.byteLength);
    }
    return null;
}

function getStyleHost(hostEl) {
    const rootNode = hostEl && typeof hostEl.getRootNode === 'function' ? hostEl.getRootNode() : null;
    // [marimo] anywidget 在 marimo 下通常跑在 ShadowRoot，需要把样式注入到 shadow 内部。
    // [ipynb] 普通文档环境注入到 document.head。
    return rootNode instanceof ShadowRoot ? rootNode : document.head;
}

function setStyleText(hostEl, styleId, content) {
    const styleHost = getStyleHost(hostEl);
    const found = styleHost.querySelector(`#${styleId}`);
    if (found instanceof HTMLStyleElement) {
        found.textContent = content;
        return;
    }
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = content;
    styleHost.appendChild(style);
}

function setError(el, message) {
    el.innerHTML = `<p style="color: red;">错误：${message}</p>`;
}

// [补丁 P0 | 通用]
// 症状：仅靠前端环境推断，行为不可控，回归难定位。
// 方案：优先使用 Python 显式传入的 target；缺失时才做环境兜底。
function resolveRenderTarget(model, el) {
    const target = model.get('target');
    if (target === 'jupyter' || target === 'marimo') {
        return target;
    }
    const rootNode = typeof el.getRootNode === 'function' ? el.getRootNode() : null;
    return rootNode instanceof ShadowRoot ? 'marimo' : 'jupyter';
}

function injectUmdScript(content) {
    const script = document.createElement('script');
    script.textContent = `
        window.ChartDashboardLib = (function() {
            var module = { exports: {} };
            var exports = module.exports;
            ${content}
            return module.exports;
        })(window);
    `;
    document.head.appendChild(script);
}

async function loadExternalAssets(el, cssPath, jsPath) {
    const styleHost = getStyleHost(el);
    await Promise.all([
        new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = cssPath;
            link.onload = resolve;
            link.onerror = reject;
            styleHost.appendChild(link);
        }),
        new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = jsPath;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        }),
    ]);
}

// [补丁集合 | 仅保留最小稳定修复]
// 注意：以下补丁都是“容器层修复”，不触碰业务数据与图表配置。
function prepareContainer(el) {
    el.classList.add('chart-dashboard-widget');
    el.style.display = 'block';
    // [补丁 P1 | 通用]
    // 症状：初次挂载时容器高度过小，图表被压缩。
    // 方案：给宿主容器设置最小可用高度，后续由图表库自行 resize。
    el.style.height = `${Math.max(520, Math.round(el.getBoundingClientRect().height || el.clientHeight || 0))}px`;
    // [ipynb] 若上游提供了 aspect-ratio，则保留（在 notebook 下用于稳定高度）。
    // [marimo] 实际是否使用 aspect-ratio 由 render() 中 target 分流控制。
    if (!el.style.aspectRatio) {
        el.style.aspectRatio = 'auto';
    }
    // [补丁 P2 | 通用]
    // 症状：父容器 overflow/max-height 裁切，导致图表显示不全或滚动异常。
    // 方案：当前宿主层统一放宽裁切约束。
    el.style.setProperty('overflow', 'visible', 'important');
    el.style.setProperty('overflow-x', 'hidden', 'important');
    el.style.setProperty('overflow-y', 'visible', 'important');
    el.style.maxHeight = 'none';

    // [补丁 P3 | marimo 主修复，ipynb 无副作用]
    // 症状：marimo anywidget 的 .contents/.marimo 高度链断裂，子图高度会塌陷。
    // 方案：仅修复这条高度链；ipynb 下选择器通常不存在，不影响 notebook。
    // [marimo] marimo 的 anywidget DOM 常见 .contents/.marimo 高度链断裂，这里只修复这条链。
    // [ipynb] 这些选择器不存在时不会生效，不影响 notebook。
    setStyleText(el, 'chart-dashboard-widget-layout-fix', `
        .chart-dashboard-widget > .contents,
        .chart-dashboard-widget > .contents > .marimo {
            display: block !important;
            height: 100% !important;
            min-height: 0 !important;
        }
    `);

    const rootNode = typeof el.getRootNode === 'function' ? el.getRootNode() : null;
    const host = rootNode instanceof ShadowRoot ? rootNode.host : null;
    if (!(host instanceof HTMLElement)) return;

    // [补丁 P4 | 通用兜底]
    // 症状：外层 output 容器有 max-height/overflow 限制，图表上下被截断。
    // 方案：放宽宿主和最近 output 容器的裁切限制。
    // [marimo/ipynb 通用兜底] 放宽宿主和最近输出容器的裁切，避免图表被父层截断。
    host.style.maxHeight = 'none';
    host.style.overflow = 'visible';

    let node = host.parentElement;
    for (let i = 0; i < 2 && node; i += 1) {
        const cls = typeof node.className === 'string' ? node.className : '';
        if (/(cell-output|output-area|marimo-output)/i.test(cls)) {
            node.style.maxHeight = 'none';
            node.style.overflow = 'visible';
            break;
        }
        node = node.parentElement;
    }
}

async function render({ model, el }) {
    const rawZipData = model.get('zip_data');
    const zipBytes = normalizeToBytes(rawZipData);
    if (!zipBytes) {
        const ctorName = rawZipData && rawZipData.constructor ? rawZipData.constructor.name : typeof rawZipData;
        console.error('❌ [ChartDashboardWidget] 未找到可识别的 ZIP 数据，收到类型:', ctorName, rawZipData);
        setError(el, `未找到图表数据（收到类型: ${ctorName}）`);
        return;
    }

    const config = model.get('config');
    const target = resolveRenderTarget(model, el);
    const aspectRatio = model.get('aspect_ratio');
    const embedFiles = model.get('embed_files');
    const cssContent = model.get('css_content');
    const jsContent = model.get('js_content');
    const cssPath = model.get('css_path');
    const libPath = model.get('lib_path');

    el.style.width = model.get('width');
    // [补丁 P5 | target 分流补丁]
    // 症状：
    // - ipynb: 清空 aspect-ratio 会导致图表压成一条线
    // - marimo: 保留 aspect-ratio 容易引入额外竖向滚动条
    // 方案：按 target 显式分流，而不是靠隐式环境猜测。
    // [ipynb] 保留 aspect-ratio，避免图表被压扁成一条线。
    // [marimo] 清空 aspect-ratio，避免出现额外竖向滚动条。
    if (target === 'jupyter' && typeof aspectRatio === 'string' && aspectRatio.trim()) {
        el.style.aspectRatio = aspectRatio;
    } else {
        el.style.aspectRatio = '';
    }

    try {
        if (embedFiles) {
            if (cssContent) setStyleText(el, 'chart-dashboard-widget-lib-css', cssContent);
            if (jsContent) injectUmdScript(jsContent);
        } else {
            await loadExternalAssets(el, cssPath, libPath);
        }
    } catch (error) {
        console.error('❌ [ChartDashboardWidget] 资源加载失败:', error);
        setError(el, `无法加载图表库 (${error.message})`);
        return;
    }

    if (typeof window.ChartDashboardLib === 'undefined' || typeof window.ChartDashboardLib.mountDashboard !== 'function') {
        console.error('❌ [ChartDashboardWidget] ChartDashboardLib 未加载');
        setError(el, '图表库未正确加载，请检查 JS 文件内容。');
        return;
    }

    try {
        prepareContainer(el);
        window.ChartDashboardLib.mountDashboard(el, { zipData: bytesToBase64(zipBytes), config });
    } catch (error) {
        console.error('❌ [ChartDashboardWidget] 图表挂载失败:', error);
        setError(el, error.message);
    }
}

export default { render };
