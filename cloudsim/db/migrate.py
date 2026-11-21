from pathlib import Path

from cloudsim.clock import utc_now_iso
from cloudsim.config import SETTING_DEFAULTS, env_db_path
from cloudsim.db.connection import connect
from cloudsim.errors import AppError

SCHEMA_VERSION = 1
SCHEMA_PATH = Path(__file__).with_name("schema_v1.sql")


def migrate(db_path=None) -> None:
    path = Path(db_path or env_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        conn.commit()
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        version = row["v"] if row else None

        if version is None:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, utc_now_iso()),
            )
            conn.commit()
        elif version < SCHEMA_VERSION:
            raise AppError(
                f"Database versi {version} lebih lama dari versi aplikasi {SCHEMA_VERSION}. "
                "Migrasi otomatis belum tersedia; buat database baru dari file backup/manual."
            )
        elif version > SCHEMA_VERSION:
            raise AppError(
                f"Database versi {version} lebih baru dari versi aplikasi {SCHEMA_VERSION}. "
                "Perbarui aplikasi atau gunakan database yang sesuai; "
                "database tidak diubah agar data tidak rusak."
            )

        now = utc_now_iso()
        for key, value in SETTING_DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_setting(key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
        conn.commit()
    finally:
        conn.close()
