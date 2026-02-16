import marimo

__generated_with = "0.19.11"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    run_button = mo.ui.run_button(label="运行 custom backtest")
    run_button
    return (run_button,)


@app.cell
def _(mo):
    # 使用内存态保存回测结果，避免 run_button 在后续重算时导致结果被清空。
    get_result, set_result = mo.state(None)
    return get_result, set_result


@app.cell
def _(get_result, run_button, set_result):
    from py_entry.example.custom_backtest import run_custom_backtest

    if run_button.value:
        # marimo 示例仅用于交互可视化，禁用保存/上传以减少副作用。
        new_result = run_custom_backtest(save_result=False, upload_result=False)
        set_result(new_result)
    result = get_result()
    return (result,)


@app.cell
def _(mo, result):
    mo.stop(result is None, mo.md("点击上方按钮运行回测。"))

    if result.summary:
        mo.md(f"### Performance\n\n`{result.summary.performance}`")
    else:
        mo.md("回测已执行，但 summary 为空。")
    return


@app.cell
def _(mo, result):
    from py_entry.io import DisplayConfig

    mo.stop(result is None)

    # 先使用默认可见配置，避免 override 把主图序列隐藏导致“渲染成功但画面空白”。
    config = DisplayConfig(
        target="marimo",
        width="100%",
        aspect_ratio="16/9",
    )
    # 直接输出 widget，避免额外布局封装影响可见性。
    chart_widget = result.display(config=config)
    chart_widget
    return


if __name__ == "__main__":
    app.run()
