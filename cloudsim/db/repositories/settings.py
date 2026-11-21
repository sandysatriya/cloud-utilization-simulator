from cloudsim.clock import utc_now_iso
from cloudsim.config import SETTING_DEFAULTS


def get_settings(conn) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM app_setting").fetchall()
    data = {r["key"]: r["value"] for r in rows}
    for key, value in SETTING_DEFAULTS.items():
        data.setdefault(key, value)
    return data


def get_float(conn, key: str, default: float) -> float:
    value = get_settings(conn).get(key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_int(conn, key: str, default: int) -> int:
    value = get_settings(conn).get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def set_setting(conn, key: str, value) -> None:
    conn.execute(
        """INSERT INTO app_setting(key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, str(value), utc_now_iso()),
    )
