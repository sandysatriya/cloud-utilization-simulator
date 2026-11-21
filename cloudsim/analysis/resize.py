from cloudsim.errors import ValidationError


def resize_value(value: float | None, source_capacity: float, target_capacity: float) -> float | None:
    if target_capacity <= 0:
        raise ValidationError("Kapasitas target harus lebih besar dari 0.")
    if value is None:
        return None
    return value * source_capacity / target_capacity


def classify_estimate(after: float | None, warning_threshold_pct: float) -> str:
    if after is None:
        return "not_available"
    if after > 100.0:
        return "over_100"
    if after >= warning_threshold_pct:
        return "near_threshold"
    return "normal"


def sufficiency_reasons(
    sample_count: int,
    completeness_pct: float | None,
    min_samples: int,
    min_completeness_pct: float,
) -> list[str]:
    reasons: list[str] = []
    if sample_count <= 0:
        reasons.append("no_samples")
    if sample_count < min_samples:
        reasons.append("low_samples")
    if completeness_pct is None:
        reasons.append("completeness_unavailable")
    elif completeness_pct < min_completeness_pct:
        reasons.append("low_completeness")
    return reasons
