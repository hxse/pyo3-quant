def choose_template(chart_count: int) -> str:
    """根据图表数量选择模板。"""
    if chart_count == 1:
        return "single"
    if chart_count == 2:
        return "horizontal-1x1"
    if chart_count == 3:
        return "vertical-1x2"
    if chart_count == 4:
        return "grid-2x2"
    return "grid-2x2"
