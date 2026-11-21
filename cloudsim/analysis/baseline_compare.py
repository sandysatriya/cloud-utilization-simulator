from cloudsim.analysis.comparison import delta_pp, metadata_differences, relative_pct
from cloudsim.enums import QUALITY_FLAGS

QUALITY_CODES = {
    "low_samples", "low_completeness", "completeness_unavailable",
    "metric_unavailable", "no_samples",
}


def _flags(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in str(value).split(",") if part.strip()}


def _quality_note(code: str, metric: str, before: set[str], after: set[str]) -> str | None:
    before_quality = before & QUALITY_CODES
    after_quality = after & QUALITY_CODES
    if before_quality == after_quality:
        return None
    before_text = ", ".join(sorted(QUALITY_FLAGS.get(f, f) for f in before_quality)) or "baik"
    after_text = ", ".join(sorted(QUALITY_FLAGS.get(f, f) for f in after_quality)) or "baik"
    return f"{code} / {metric}: kualitas berubah ({before_text} -> {after_text})"


def compare_baseline(baseline: dict, analysis) -> dict:
    baseline_stats = {(s["server_code"], s["metric"]): s for s in baseline["stats"]}
    current_stats = {(s.server.code, s.metric): s for s in analysis.stats}

    scope_before = {code for code, _ in baseline_stats}
    scope_after = {code for code, _ in current_stats}
    scope_added = sorted(scope_after - scope_before)
    scope_removed = sorted(scope_before - scope_after)

    exclusion_before = {e["server_code"]: e for e in baseline["exclusions"]}
    exclusion_after = {e.server_code: e for e in analysis.exclusions}
    exclusion_added = sorted(set(exclusion_after) - set(exclusion_before))
    exclusion_removed = sorted(set(exclusion_before) - set(exclusion_after))
    exclusion_changed = []
    for code in sorted(set(exclusion_before) & set(exclusion_after)):
        old = exclusion_before[code]
        new = exclusion_after[code]
        if (old.get("source"), old.get("reason")) != (new.source, new.reason):
            exclusion_changed.append(code)

    metadata_changes: list[str] = []
    for metric in ("cpu", "memory"):
        old_sources = [s for s in baseline["sources"] if s["metric"] == metric]
        old_type = old_sources[0]["statistic_type"] if old_sources else None
        old_interval = old_sources[0]["interval_seconds"] if old_sources else None
        differences = metadata_differences(
            old_type, old_interval,
            analysis.stat_type_by_metric.get(metric),
            analysis.interval_by_metric.get(metric),
            baseline.get("formula_version"), analysis.formula_version,
        )
        metadata_changes.extend(f"{metric}: {item}" for item in differences)
    metadata_changes = list(dict.fromkeys(metadata_changes))

    inventory_changes: list[str] = []
    for (code, metric), old in baseline_stats.items():
        new = current_stats.get((code, metric))
        if not new:
            continue
        if int(old["vcpu"]) != int(new.server.vcpu) or float(old["ram_gib"]) != float(new.server.ram_gib):
            inventory_changes.append(
                f"{code}: kapasitas inventaris berubah "
                f"({old['vcpu']} vCPU/{old['ram_gib']} GiB -> "
                f"{new.server.vcpu} vCPU/{new.server.ram_gib} GiB)"
            )
        old_env = old.get("environment")
        new_env = new.server.environment
        if old_env != new_env:
            inventory_changes.append(f"{code}: environment berubah ({old_env} -> {new_env})")

    quality_changes: list[str] = []
    rows: list[dict] = []
    for key in sorted(set(baseline_stats) | set(current_stats)):
        code, metric = key
        old = baseline_stats.get(key)
        new = current_stats.get(key)
        old_values = {
            "avg": old["avg_value"] if old else None,
            "p95": old["p95_value"] if old else None,
            "max": old["max_value"] if old else None,
        }
        new_values = {
            "avg": new.avg if new else None,
            "p95": new.p95 if new else None,
            "max": new.max if new else None,
        }
        deltas = {}
        for stat in ("avg", "p95", "max"):
            deltas[stat] = {
                "pp": delta_pp(old_values[stat], new_values[stat]),
                "relative_pct": relative_pct(old_values[stat], new_values[stat]),
            }
        before_flags = _flags(old.get("quality_flags") if old else None)
        after_flags = set(new.flags) if new else set()
        note = _quality_note(code, metric, before_flags, after_flags)
        if note:
            quality_changes.append(note)
        rows.append({
            "server_code": code,
            "metric": metric,
            "in_baseline": old is not None,
            "in_current": new is not None,
            "before": old_values,
            "after": new_values,
            "delta": deltas,
            "before_samples": old["sample_count"] if old else None,
            "after_samples": new.sample_count if new else None,
            "before_completeness": old["completeness_pct"] if old else None,
            "after_completeness": new.completeness_pct if new else None,
            "before_flags": sorted(before_flags),
            "after_flags": sorted(after_flags),
            "quality_changed": note is not None,
        })

    return {
        "baseline_id": baseline["id"],
        "baseline_name": baseline["name"],
        "baseline_created_at": baseline["created_at"],
        "baseline_formula_version": baseline.get("formula_version"),
        "current_formula_version": analysis.formula_version,
        "scope_added": scope_added,
        "scope_removed": scope_removed,
        "exclusion_added": exclusion_added,
        "exclusion_removed": exclusion_removed,
        "exclusion_changed": exclusion_changed,
        "inventory_changes": sorted(set(inventory_changes)),
        "metadata_changes": metadata_changes,
        "quality_changes": quality_changes,
        "comparable": not metadata_changes,
        "rows": rows,
    }
