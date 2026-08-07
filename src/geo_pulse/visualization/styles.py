def residual_color(value: float) -> str:
    if value > 0.15:
        return "#d73027"
    if value < -0.15:
        return "#4575b4"
    return "#74add1" if value < 0 else "#f46d43"
