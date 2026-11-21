from cloudsim.errors import ValidationError

ALLOWED_MEASURES = ("avg", "p95", "max")
ALLOWED_AGGREGATES = ("none", "simple_mean", "capacity_weighted_vcpu", "capacity_weighted_ram")
ALLOWED_OPERATORS = ("lte", "gte", "between")
ALLOWED_METRICS = ("cpu", "memory")


def validate_thresholds(thresholds: list[dict]) -> None:
    ranges = []
    for item in thresholds:
        low = item.get("min_value")
        high = item.get("max_value")
        if low is None and high is None:
            raise ValidationError("Setiap batas capaian harus memiliki minimal satu batas angka.")
        if low is not None and high is not None and low > high:
            raise ValidationError("Batas bawah capaian tidak boleh lebih besar dari batas atas.")
        ranges.append((low, high))
    for i, (low_a, high_a) in enumerate(ranges):
        for low_b, high_b in ranges[i + 1:]:
            lower = max(float("-inf") if low_a is None else low_a,
                        float("-inf") if low_b is None else low_b)
            upper = min(float("inf") if high_a is None else high_a,
                        float("inf") if high_b is None else high_b)
            if lower < upper:
                raise ValidationError("Rentang batas capaian saling tumpang tindih.")


def validate_definition(definition: dict, approve: bool = False) -> None:
    if approve:
        if definition.get("metric") not in ALLOWED_METRICS:
            raise ValidationError("KPI yang disetujui harus memilih metrik CPU atau memory.")
        if definition.get("measure") not in ALLOWED_MEASURES:
            raise ValidationError("Measure KPI tidak valid.")
        if definition.get("aggregate_method") not in ALLOWED_AGGREGATES:
            raise ValidationError("Metode agregasi KPI tidak valid.")
        if definition.get("operator") not in ALLOWED_OPERATORS:
            raise ValidationError("Operator KPI tidak valid.")
        if definition.get("target_value") is None:
            raise ValidationError("Target KPI wajib diisi sebelum disetujui.")
        if definition.get("operator") == "between" and definition.get("target_value_upper") is None:
            raise ValidationError("Operator 'between' memerlukan batas atas.")
        upper = definition.get("target_value_upper")
        if upper is not None and upper < definition["target_value"]:
            raise ValidationError("Batas atas KPI tidak boleh lebih kecil dari target.")
        if definition.get("scope_mode") == "baseline_scope" and not definition.get("baseline_id"):
            raise ValidationError("Mode scope baseline memerlukan baseline yang dipilih.")


def aggregate_value(rows: list[tuple[float, float | None]], method: str) -> float | None:
    if not rows:
        return None
    values = [value for value, _ in rows]
    if method == "simple_mean":
        return sum(values) / len(values)
    if method in {"capacity_weighted_vcpu", "capacity_weighted_ram"}:
        weighted = [(value, weight) for value, weight in rows if weight and weight > 0]
        total_weight = sum(weight for _, weight in weighted)
        if total_weight <= 0:
            return None
        return sum(value * weight for value, weight in weighted) / total_weight
    if method == "none":
        return None
    raise ValidationError("Metode agregasi KPI tidak dikenal.")


def evaluate(value: float | None, operator: str, target: float, upper: float | None = None) -> bool | None:
    if value is None:
        return None
    if operator == "lte":
        return value <= target
    if operator == "gte":
        return value >= target
    if operator == "between":
        if upper is None:
            return None
        return target <= value <= upper
    raise ValidationError("Operator KPI tidak dikenal.")


def compute_kpi(definition: dict, stats: list) -> dict:
    status = definition.get("status")
    if status != "approved":
        return {
            "available": False,
            "reason": "KPI belum disetujui.",
            "status": status or "unconfigured",
        }

    metric = definition["metric"]
    measure = definition["measure"]
    rows = []
    for item in stats:
        if item.metric != metric:
            continue
        value = getattr(item, measure, None)
        if value is None:
            continue
        weight = item.server.vcpu if definition["aggregate_method"] == "capacity_weighted_vcpu" else item.server.ram_gib
        rows.append((value, weight, item))

    aggregate = aggregate_value([(v, w) for v, w, _ in rows], definition["aggregate_method"])
    target = float(definition["target_value"])
    upper = definition.get("target_value_upper")
    if definition["aggregate_method"] == "none":
        per_server = []
        for value, _, item in rows:
            per_server.append({
                "server_code": item.server.code,
                "value": value,
                "passed": evaluate(value, definition["operator"], target, upper),
            })
        passed_count = sum(1 for row in per_server if row["passed"])
        return {
            "available": True,
            "metric": metric,
            "measure": measure,
            "aggregate_method": definition["aggregate_method"],
            "aggregate_value": None,
            "per_server": per_server,
            "passed_count": passed_count,
            "total_count": len(per_server),
            "evaluated": None,
        }

    return {
        "available": True,
        "metric": metric,
        "measure": measure,
        "aggregate_method": definition["aggregate_method"],
        "aggregate_value": aggregate,
        "per_server": [
            {"server_code": item.server.code, "value": value}
            for value, _, item in rows
        ],
        "passed_count": None,
        "total_count": len(rows),
        "evaluated": evaluate(aggregate, definition["operator"], target, upper),
    }
