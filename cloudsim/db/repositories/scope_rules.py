from cloudsim.clock import utc_now_iso
from cloudsim.enums import SCOPE_DIMENSIONS
from cloudsim.errors import ValidationError


def list_rules(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM scope_rule ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_rule(conn, rule_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM scope_rule WHERE id = ?", (rule_id,)).fetchone()
    return dict(row) if row else None


def validate_rule(data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    dimension = data.get("dimension")
    match_value = str(data.get("match_value") or "").strip()
    reason = str(data.get("reason") or "").strip()
    if not name:
        raise ValidationError("Nama aturan wajib diisi.")
    if dimension not in SCOPE_DIMENSIONS:
        raise ValidationError("Dimensi aturan tidak valid.")
    if not match_value:
        raise ValidationError("Nilai yang dicocokkan wajib diisi.")
    if not reason:
        raise ValidationError("Alasan pengecualian wajib diisi.")
    return {
        "name": name,
        "dimension": dimension,
        "match_value": match_value,
        "reason": reason,
        "active": 1 if data.get("active", True) else 0,
    }


def create_rule(conn, data: dict) -> int:
    clean = validate_rule(data)
    now = utc_now_iso()
    cur = conn.execute(
        """INSERT INTO scope_rule(name, dimension, match_value, reason, active, created_at, updated_at)
           VALUES (:name, :dimension, :match_value, :reason, :active, :created_at, :updated_at)""",
        {**clean, "created_at": now, "updated_at": now},
    )
    return int(cur.lastrowid)


def update_rule(conn, rule_id: int, data: dict) -> None:
    clean = validate_rule(data)
    conn.execute(
        """UPDATE scope_rule SET name=:name, dimension=:dimension, match_value=:match_value,
           reason=:reason, active=:active, updated_at=:updated_at WHERE id=:id""",
        {**clean, "id": rule_id, "updated_at": utc_now_iso()},
    )


def delete_rule(conn, rule_id: int) -> None:
    conn.execute("DELETE FROM scope_rule WHERE id = ?", (rule_id,))
