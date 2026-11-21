import math


def arithmetic_mean(values) -> float | None:
    values = [float(v) for v in values]
    if not values:
        return None
    return sum(values) / len(values)


def percentile_linear(values, q: float) -> float | None:
    data = sorted(float(v) for v in values)
    n = len(data)
    if n == 0:
        return None
    if n == 1:
        return data[0]
    position = (n - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return data[lower]
    fraction = position - lower
    return data[lower] + fraction * (data[upper] - data[lower])


def p95(values) -> float | None:
    return percentile_linear(values, 0.95)


def maximum(values) -> float | None:
    values = [float(v) for v in values]
    return max(values) if values else None


def stat_bundle(values) -> dict:
    return {
        "avg": arithmetic_mean(values),
        "p95": p95(values),
        "max": maximum(values),
    }


def interval_phrase(seconds: int | None) -> str:
    if seconds is None:
        return "interval tidak diketahui"
    if seconds % 86400 == 0:
        count = seconds // 86400
        return "per hari" if count == 1 else f"per {count} hari"
    if seconds % 3600 == 0:
        count = seconds // 3600
        return "per jam" if count == 1 else f"per {count} jam"
    if seconds % 60 == 0:
        count = seconds // 60
        return "per menit" if count == 1 else f"per {count} menit"
    return f"per {seconds} detik"


def source_phrase(stat_type: str | None, interval_seconds: int | None, custom_label: str | None = None) -> str:
    phrase = interval_phrase(interval_seconds)
    if stat_type == "average":
        return f"rata-rata {phrase}"
    if stat_type == "maximum":
        return f"maksimum {phrase}"
    if stat_type == "other":
        return custom_label or "statistik lain yang diisi pengguna"
    return "statistik sumber tidak diketahui"


def stat_phrase(stat_name: str, stat_type: str | None, interval_seconds: int | None,
                custom_label: str | None = None) -> str:
    source = source_phrase(stat_type, interval_seconds, custom_label)
    if stat_type == "average":
        return {
            "avg": f"Rata-rata {interval_phrase(interval_seconds)}",
            "p95": f"P95 {source}",
            "max": f"Maksimum {source}",
        }[stat_name]
    return {
        "avg": f"Rata-rata dari {source}",
        "p95": f"P95 dari {source}",
        "max": f"Maksimum dari {source}",
    }[stat_name]
