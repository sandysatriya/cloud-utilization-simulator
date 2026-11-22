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

