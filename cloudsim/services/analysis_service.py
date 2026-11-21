from collections import defaultdict

from cloudsim.analysis.completeness import completeness_pct, expected_sample_count
from cloudsim.analysis.models import AnalysisResult, MetricStats
from cloudsim.analysis.scope import effective_exclusions
from cloudsim.analysis.stats import stat_bundle
from cloudsim.config import (
    FORMULA_VERSION_STATS,
    P95_METHOD,
)
from cloudsim.db.connection import read_connection
from cloudsim.db.repositories import batches as batch_repo
from cloudsim.db.repositories import samples as sample_repo
from cloudsim.db.repositories import scope_rules as rule_repo
from cloudsim.db.repositories import servers as server_repo
from cloudsim.db.repositories import settings as settings_repo
from cloudsim.errors import AnalysisError, ValidationError
from cloudsim.io.parsers import validate_timezone


def _load_batches(conn, ids: list[int], metric: str) -> list:
    batches = []
    for batch_id in ids:
        batch = batch_repo.get_batch(conn, int(batch_id))
        if batch is None:
            raise AnalysisError(f"Batch #{batch_id} tidak ditemukan.")
        if batch.data_type != metric:
            raise AnalysisError(
                f"Batch #{batch_id} bertipe {batch.data_type}, bukan {metric}."
            )
        batches.append(batch)
    return batches


def _resolve_metadata(batches: list, metric: str, warnings: list[str]):
    if not batches:
        return None, None
    types = {b.statistic_type for b in batches}
    if len(types) > 1:
        names = ", ".join(sorted(t or "tidak diketahui" for t in types))
        raise AnalysisError(
            f"Batch {metric} memiliki jenis statistik berbeda ({names}). "
            "Normalisasi belum tersedia; pilih batch dengan metadata yang sama."
        )
    statistic_type = next(iter(types))
    if any(b.interval_seconds is None for b in batches):
        warnings.append(
            f"Sebagian batch {metric} tidak memiliki interval; kelengkapan data tidak dihitung."
        )
        return statistic_type, None
    intervals = {b.interval_seconds for b in batches}
    if len(intervals) > 1:
        values = ", ".join(str(v) for v in sorted(intervals))
        raise AnalysisError(
            f"Batch {metric} memiliki interval berbeda ({values} detik). "
            "Pencampuran interval belum didukung; pilih batch dengan interval yang sama."
        )
    return statistic_type, next(iter(intervals))


def analyze(
    window_start_utc: int,
    window_end_utc: int,
    cpu_batch_ids: list[int],
    memory_batch_ids: list[int],
    display_timezone: str,
    *,
    db_path=None,
) -> AnalysisResult:
    if window_end_utc <= window_start_utc:
        raise AnalysisError("Akhir periode harus setelah awal periode.")
    validate_timezone(display_timezone)

    warnings: list[str] = []
    with read_connection(db_path) as conn:
        settings = settings_repo.get_settings(conn)
        servers = server_repo.list_servers(conn)
        rules = rule_repo.list_rules(conn)
        cpu_batches = _load_batches(conn, cpu_batch_ids, "cpu")
        memory_batches = _load_batches(conn, memory_batch_ids, "memory")
        exclusions = effective_exclusions(servers, rules)
        excluded = {e.server_code for e in exclusions}
        included = [s for s in servers if s.code not in excluded]

        stat_type_by_metric: dict[str, str | None] = {}
        interval_by_metric: dict[str, int | None] = {}
        for metric, batches in (("cpu", cpu_batches), ("memory", memory_batches)):
            stat_type, interval = _resolve_metadata(batches, metric, warnings)
            stat_type_by_metric[metric] = stat_type
            interval_by_metric[metric] = interval
            if not batches:
                warnings.append(f"Tidak ada batch {metric} dipilih; statistik {metric} tidak tersedia.")

        min_samples = int(float(settings.get("min_samples", 24)))
        min_completeness = float(settings.get("min_completeness_pct", 80))

        stats: list[MetricStats] = []
        server_ids = [s.id for s in included]
        for metric, batches in (("cpu", cpu_batches), ("memory", memory_batches)):
            if batches and server_ids:
                series_map = sample_repo.fetch_samples(
                    conn, server_ids, metric, window_start_utc, window_end_utc,
                    batch_ids=[b.id for b in batches],
                )
            else:
                series_map = {}
            interval = interval_by_metric[metric]
            for server in included:
                series = series_map.get(server.id, [])
                values = [value for _, value in series]
                sample_count = len(values)
                expected = (
                    expected_sample_count(window_start_utc, window_end_utc, interval)
                    if batches else None
                )
                completeness = completeness_pct(sample_count, expected)
                bundle = stat_bundle(values)
                flags: list[str] = []
                if not batches:
                    flags.append("metric_unavailable")
                else:
                    if sample_count == 0:
                        flags.append("no_samples")
                    if sample_count < min_samples:
                        flags.append("low_samples")
                    if completeness is None:
                        flags.append("completeness_unavailable")
                    elif completeness < min_completeness:
                        flags.append("low_completeness")
                stats.append(MetricStats(
                    server=server,
                    metric=metric,
                    sample_count=sample_count,
                    expected_count=expected,
                    completeness_pct=completeness,
                    avg=bundle["avg"],
                    p95=bundle["p95"],
                    max=bundle["max"],
                    flags=flags,
                    series=series,
                ))

    return AnalysisResult(
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        display_timezone=display_timezone,
        formula_version=FORMULA_VERSION_STATS,
        p95_method=P95_METHOD,
        servers=servers,
        exclusions=exclusions,
        cpu_batches=cpu_batches,
        memory_batches=memory_batches,
        stats=stats,
        warnings=warnings,
        stat_type_by_metric=stat_type_by_metric,
        interval_by_metric=interval_by_metric,
        min_samples=min_samples,
        min_completeness_pct=min_completeness,
    )


def aggregate_stats(stats: list[MetricStats], metric: str, measure: str, method: str) -> dict:
    included = [
        item for item in stats
        if item.metric == metric and getattr(item, measure, None) is not None
    ]
    rows = []
    for item in included:
        weight = item.server.vcpu if method == "capacity_weighted_vcpu" else item.server.ram_gib
        rows.append((getattr(item, measure), weight))
    value = None
    if rows and method == "simple_mean":
        value = sum(v for v, _ in rows) / len(rows)
    elif rows and method in {"capacity_weighted_vcpu", "capacity_weighted_ram"}:
        total_weight = sum(w for _, w in rows)
        if total_weight > 0:
            value = sum(v * w for v, w in rows) / total_weight
    total_for_metric = sum(1 for item in stats if item.metric == metric)
    return {
        "value": value,
        "calculated": len(included),
        "total_servers": total_for_metric,
        "method": method,
        "measure": measure,
        "metric": metric,
    }


def server_comparison_rows(stats: list[MetricStats]) -> list[dict]:
    rows = []
    grouped = defaultdict(dict)
    for item in stats:
        grouped[item.server.code][item.metric] = item
    for code, metrics in grouped.items():
        row = {"server_code": code}
        for metric in ("cpu", "memory"):
            item = metrics.get(metric)
            row[f"{metric}_avg"] = item.avg if item else None
            row[f"{metric}_p95"] = item.p95 if item else None
            row[f"{metric}_max"] = item.max if item else None
            row[f"{metric}_completeness"] = item.completeness_pct if item else None
            row[f"{metric}_samples"] = item.sample_count if item else 0
            row[f"{metric}_flags"] = ", ".join(item.flags) if item else ""
        rows.append(row)
    return rows
