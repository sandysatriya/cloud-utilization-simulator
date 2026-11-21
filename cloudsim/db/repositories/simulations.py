import json

from cloudsim.analysis.models import AnalysisResult, Server
from cloudsim.clock import utc_now_iso


def save_simulation(
    conn,
    *,
    name: str,
    server: Server,
    analysis: AnalysisResult,
    target_vcpu: int,
    target_ram_gib: float,
    target_instance_type: str | None,
    warning_threshold_pct: float,
    data_sufficient: bool,
    results: list[dict],
    notes: str | None,
    target_price: dict | None,
    completeness_pct: float | None = None,
) -> int:
    source_snapshot = json.dumps([
        {
            "id": b.id, "file_name": b.file_name, "sha256": b.file_sha256,
            "timezone": b.timezone, "interval_seconds": b.interval_seconds,
            "statistic_type": b.statistic_type, "statistic_label": b.statistic_label,
        }
        for b in [*analysis.cpu_batches, *analysis.memory_batches]
    ])
    cpu_type = analysis.stat_type_by_metric.get("cpu")
    memory_type = analysis.stat_type_by_metric.get("memory")
    combined_type = f"cpu={cpu_type or 'unknown'};memory={memory_type or 'unknown'}"
    labels = []
    for metric in ("cpu", "memory"):
        batches = analysis.batches_for(metric)
        if batches and batches[0].statistic_label:
            labels.append(f"{metric}: {batches[0].statistic_label}")
    completeness = analysis.stats_for(server.code, "cpu")
    if completeness_pct is None:
        completeness_pct = completeness.completeness_pct if completeness else None
    target_price = target_price or {}
    cur = conn.execute(
        """INSERT INTO simulation(name, created_at, server_code, server_name, environment,
           region, workload, window_start_utc, window_end_utc, display_timezone,
           statistic_type, statistic_label, interval_seconds, source_batch_snapshot,
           source_vcpu, source_ram_gib, target_vcpu, target_ram_gib, target_instance_type,
           warning_threshold_pct, completeness_pct, data_sufficient, formula_version,
           target_price_amount, target_price_currency, target_price_unit,
           target_price_unit_label, target_price_source_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name, utc_now_iso(), server.code, server.name, server.environment, server.region,
            server.workload, analysis.window_start_utc, analysis.window_end_utc,
            analysis.display_timezone, combined_type, "; ".join(labels) or None,
            analysis.interval_by_metric.get("cpu") or analysis.interval_by_metric.get("memory"),
            source_snapshot, server.vcpu, server.ram_gib, target_vcpu, target_ram_gib,
            target_instance_type, warning_threshold_pct, completeness_pct,
            1 if data_sufficient else 0, analysis.formula_version,
            target_price.get("amount"), target_price.get("currency"),
            target_price.get("unit"), target_price.get("unit_label"),
            target_price.get("source_date"), notes,
        ),
    )
    simulation_id = int(cur.lastrowid)
    conn.executemany(
        """INSERT INTO simulation_result(simulation_id, metric, stat_name, before_value,
           after_value, flag) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (simulation_id, r["metric"], r["stat_name"], r.get("before"), r.get("after"), r["flag"])
            for r in results
        ],
    )
    return simulation_id


def list_simulations(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM simulation ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_simulation(conn, simulation_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM simulation WHERE id = ?", (simulation_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["results"] = [dict(r) for r in conn.execute(
        "SELECT * FROM simulation_result WHERE simulation_id = ? ORDER BY metric, stat_name",
        (simulation_id,),
    ).fetchall()]
    return data


def delete_simulation(conn, simulation_id: int) -> None:
    conn.execute("DELETE FROM simulation WHERE id = ?", (simulation_id,))
