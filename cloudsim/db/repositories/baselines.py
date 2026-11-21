from cloudsim.analysis.models import AnalysisResult
from cloudsim.clock import utc_now_iso


def create_baseline(conn, name: str, analysis: AnalysisResult, notes: str | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO baseline(name, created_at, window_start_utc, window_end_utc,
           display_timezone, formula_version, notes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            name, utc_now_iso(), analysis.window_start_utc, analysis.window_end_utc,
            analysis.display_timezone, analysis.formula_version, notes,
        ),
    )
    baseline_id = int(cur.lastrowid)

    for batch in [*analysis.cpu_batches, *analysis.memory_batches]:
        accepted = conn.execute(
            "SELECT COUNT(*) AS c FROM utilization_sample WHERE batch_id = ?", (batch.id,)
        ).fetchone()["c"]
        conn.execute(
            """INSERT INTO baseline_source(baseline_id, metric, batch_id, file_name, file_sha256,
               timezone, interval_seconds, statistic_type, statistic_label, data_start_utc,
               data_end_utc, sample_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                baseline_id, batch.metric, batch.id, batch.file_name, batch.file_sha256,
                batch.timezone, batch.interval_seconds, batch.statistic_type,
                batch.statistic_label, batch.period_start_utc, batch.period_end_utc, accepted,
            ),
        )

    for exclusion in analysis.exclusions:
        conn.execute(
            """INSERT INTO baseline_exclusion(baseline_id, server_code, server_name, source,
               rule_name, reason) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                baseline_id, exclusion.server_code, exclusion.server_name, exclusion.source,
                exclusion.rule_name, exclusion.reason,
            ),
        )

    for stat in analysis.stats:
        conn.execute(
            """INSERT INTO baseline_server_stat(baseline_id, server_code, environment, workload,
               vcpu, ram_gib, metric, sample_count, completeness_pct, avg_value, p95_value,
               max_value, quality_flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                baseline_id, stat.server.code, stat.server.environment, stat.server.workload,
                stat.server.vcpu, stat.server.ram_gib, stat.metric, stat.sample_count,
                stat.completeness_pct, stat.avg, stat.p95, stat.max, ",".join(stat.flags),
            ),
        )
    return baseline_id


def list_baselines(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT b.*,
                  (SELECT COUNT(DISTINCT server_code) FROM baseline_server_stat s
                   WHERE s.baseline_id = b.id) AS server_count
           FROM baseline b ORDER BY b.id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_baseline(conn, baseline_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM baseline WHERE id = ?", (baseline_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["sources"] = [dict(r) for r in conn.execute(
        "SELECT * FROM baseline_source WHERE baseline_id = ? ORDER BY metric, id", (baseline_id,)
    ).fetchall()]
    data["exclusions"] = [dict(r) for r in conn.execute(
        "SELECT * FROM baseline_exclusion WHERE baseline_id = ? ORDER BY server_code", (baseline_id,)
    ).fetchall()]
    data["stats"] = [dict(r) for r in conn.execute(
        "SELECT * FROM baseline_server_stat WHERE baseline_id = ? ORDER BY server_code, metric",
        (baseline_id,),
    ).fetchall()]
    return data


def delete_baseline(conn, baseline_id: int) -> None:
    conn.execute("DELETE FROM baseline WHERE id = ?", (baseline_id,))
