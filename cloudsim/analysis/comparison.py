def delta_pp(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return b - a


def relative_pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0:
        return None
    return (b - a) / a * 100.0


def metadata_differences(
    a_stat_type: str | None,
    a_interval: int | None,
    b_stat_type: str | None,
    b_interval: int | None,
    a_formula: str | None = None,
    b_formula: str | None = None,
) -> list[str]:
    differences: list[str] = []
    if a_stat_type != b_stat_type:
        differences.append("jenis statistik sumber berbeda")
    if a_interval != b_interval:
        differences.append("interval sumber berbeda")
    if a_formula and b_formula and a_formula != b_formula:
        differences.append("versi formula berbeda")
    return differences


def is_comparable(a_stat_type, a_interval, b_stat_type, b_interval) -> bool:
    return a_stat_type == b_stat_type and a_interval == b_interval
