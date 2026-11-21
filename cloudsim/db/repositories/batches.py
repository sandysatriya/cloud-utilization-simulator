from cloudsim.analysis.models import Batch
from cloudsim.clock import utc_now_iso


def row_to_batch(row) -> Batch:
    return Batch(
        id=row["id"],
        data_type=row["data_type"],
        file_name=row["file_name"],
        file_sha256=row["file_sha256"],
        timezone=row["timezone"],
        interval_seconds=row["interval_seconds"],
        statistic_type=row["statistic_type"],
        statistic_label=row["statistic_label"],
        period_start_utc=row["period_start_utc"],
        period_end_utc=row["period_end_utc"],
        total_rows=row["total_rows"],
        accepted_rows=row["accepted_rows"],
        rejected_rows=row["rejected_rows"],
        imported_at=row["imported_at"],
        notes=row["notes"],
    )


def create_batch(
    conn,
    *,
    data_type: str,
    file_name: str,
    file_sha256: str,
    timezone: str | None = None,
    interval_seconds: int | None = None,
    statistic_type: str | None = None,
    statistic_label: str | None = None,
    period_start_utc: int | None = None,
    period_end_utc: int | None = None,
    total_rows: int = 0,
    accepted_rows: int = 0,
    rejected_rows: int = 0,
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO import_batch(data_type, file_name, file_sha256, timezone, interval_seconds,
           statistic_type, statistic_label, period_start_utc, period_end_utc, total_rows,
           accepted_rows, rejected_rows, imported_at, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data_type, file_name, file_sha256, timezone, interval_seconds, statistic_type,
            statistic_label, period_start_utc, period_end_utc, total_rows, accepted_rows,
            rejected_rows, utc_now_iso(), notes,
        ),
    )
    return int(cur.lastrowid)


def add_issues(conn, batch_id: int, issues: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO import_issue(batch_id, severity, code, row_ref, detail) VALUES (?, ?, ?, ?, ?)",
        [
            (batch_id, item.get("severity", "error"), item.get("code", "issue"),
             str(item.get("row_ref") or ""), item.get("detail", ""))
            for item in issues
        ],
    )


def list_batches(conn, data_type: str | None = None) -> list[Batch]:
    if data_type:
        rows = conn.execute(
            "SELECT * FROM import_batch WHERE data_type = ? ORDER BY id DESC", (data_type,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM import_batch ORDER BY id DESC").fetchall()
    return [row_to_batch(r) for r in rows]


def get_batch(conn, batch_id: int) -> Batch | None:
    row = conn.execute("SELECT * FROM import_batch WHERE id = ?", (batch_id,)).fetchone()
    return row_to_batch(row) if row else None


def find_batch_by_hash(conn, file_sha256: str):
    return conn.execute(
        "SELECT * FROM import_batch WHERE file_sha256 = ? ORDER BY id DESC LIMIT 1",
        (file_sha256,),
    ).fetchone()


def list_issues(conn, batch_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM import_issue WHERE batch_id = ? ORDER BY id", (batch_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def delete_batch(conn, batch_id: int) -> None:
    conn.execute("DELETE FROM import_batch WHERE id = ?", (batch_id,))
