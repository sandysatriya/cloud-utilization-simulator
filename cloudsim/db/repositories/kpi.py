from cloudsim.clock import utc_now_iso
from cloudsim.config import FORMULA_VERSION_KPI


def list_definitions(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM kpi_definition ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_definition(conn, kpi_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM kpi_definition WHERE id = ?", (kpi_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["thresholds"] = [dict(r) for r in conn.execute(
        "SELECT * FROM kpi_threshold WHERE kpi_id = ? ORDER BY COALESCE(min_value, 0)",
        (kpi_id,),
    ).fetchall()]
    return data


def save_definition(conn, data: dict, thresholds: list[dict] | None = None,
                    kpi_id: int | None = None, approve: bool = False) -> int:
    now = utc_now_iso()
    status = "approved" if approve else "draft"
    approved_at = now if approve else None
    values = {
        "name": data.get("name") or "KPI tanpa nama",
        "description": data.get("description"),
        "status": status,
        "metric": data.get("metric"),
        "measure": data.get("measure"),
        "aggregate_method": data.get("aggregate_method"),
        "operator": data.get("operator"),
        "target_value": data.get("target_value"),
        "target_value_upper": data.get("target_value_upper"),
        "scope_mode": data.get("scope_mode") or "current_scope",
        "baseline_id": data.get("baseline_id"),
        "approved_at": approved_at,
        "formula_version": FORMULA_VERSION_KPI if approve else None,
        "updated_at": now,
    }
    if kpi_id is None:
        values["created_at"] = now
        cur = conn.execute(
            """INSERT INTO kpi_definition(name, description, status, metric, measure,
               aggregate_method, operator, target_value, target_value_upper, scope_mode,
               baseline_id, approved_at, formula_version, created_at, updated_at)
               VALUES (:name, :description, :status, :metric, :measure, :aggregate_method,
               :operator, :target_value, :target_value_upper, :scope_mode, :baseline_id,
               :approved_at, :formula_version, :created_at, :updated_at)""",
            values,
        )
        kpi_id = int(cur.lastrowid)
    else:
        conn.execute(
            """UPDATE kpi_definition SET name=:name, description=:description, status=:status,
               metric=:metric, measure=:measure, aggregate_method=:aggregate_method,
               operator=:operator, target_value=:target_value,
               target_value_upper=:target_value_upper, scope_mode=:scope_mode,
               baseline_id=:baseline_id, approved_at=:approved_at,
               formula_version=:formula_version, updated_at=:updated_at WHERE id=:id""",
            {**values, "id": kpi_id},
        )
    if thresholds is not None:
        conn.execute("DELETE FROM kpi_threshold WHERE kpi_id = ?", (kpi_id,))
        conn.executemany(
            "INSERT INTO kpi_threshold(kpi_id, label, min_value, max_value, meaning) VALUES (?, ?, ?, ?, ?)",
            [
                (kpi_id, t.get("label") or "Batas", t.get("min_value"), t.get("max_value"),
                 t.get("meaning"))
                for t in thresholds
            ],
        )
    return kpi_id


def revoke_definition(conn, kpi_id: int) -> None:
    conn.execute(
        "UPDATE kpi_definition SET status='draft', approved_at=NULL, formula_version=NULL, "
        "updated_at=? WHERE id=?",
        (utc_now_iso(), kpi_id),
    )


def delete_definition(conn, kpi_id: int) -> None:
    conn.execute("DELETE FROM kpi_definition WHERE id = ?", (kpi_id,))
