def expected_sample_count(start_utc: int, end_utc: int, interval_seconds: int | None) -> int | None:
    if not interval_seconds or interval_seconds <= 0:
        return None
    duration = end_utc - start_utc
    if duration <= 0:
        return None
    return duration // interval_seconds


def completeness_pct(available: int, expected: int | None) -> float | None:
    if expected is None or expected <= 0:
        return None
    return available / expected * 100.0


def preview_completeness_pct(sample_count: int, first_ts: int | None, last_ts: int | None,
                             interval_seconds: int | None) -> float | None:
    """Kelengkapan berdasarkan rentang data yang diamati (untuk laporan preview import)."""
    if first_ts is None or last_ts is None or not interval_seconds:
        return None
    if last_ts < first_ts:
        return None
    expected = (last_ts - first_ts) // interval_seconds + 1
    return completeness_pct(sample_count, expected)
