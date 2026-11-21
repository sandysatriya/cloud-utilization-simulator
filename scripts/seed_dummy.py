"""Seed database dengan dataset dummy deterministik.

Jalankan hanya untuk pengembangan. Script ini mengimpor file di dummy_data/
melalui service yang sama dengan aplikasi, sehingga validasi tetap berlaku.
"""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cloudsim.config import DEFAULT_DISPLAY_TZ, env_db_path
from cloudsim.db.connection import read_connection
from cloudsim.db.migrate import migrate
from cloudsim.errors import AppError
from cloudsim.io.column_mapping import INVENTORY_FIELDS, TIMESERIES_FIELDS
from cloudsim.services import (
    baseline_service,
    inventory_import_service,
    scope_service,
    timeseries_import_service,
)
from cloudsim.services.analysis_service import analyze

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "dummy_data"
TIMEZONE = "Asia/Jakarta"


def _mapping(fields: list[dict]) -> dict:
    return {field["key"]: field["label"] for field in fields}


def _count_servers(db_path) -> int:
    with read_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM server").fetchone()
    return int(row["c"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed dataset dummy.")
    parser.add_argument("--db", type=Path, default=env_db_path())
    parser.add_argument(
        "--reset", action="store_true",
        help="Hapus file database yang ada sebelum seed (tidak dapat dibatalkan).",
    )
    args = parser.parse_args()
    db_path: Path = args.db

    if args.reset and db_path.exists():
        print(f"Menghapus database lama: {db_path}")
        db_path.unlink()
    migrate(db_path)
    if _count_servers(db_path) > 0:
        print(
            "Database sudah berisi server. Seed dibatalkan agar tidak menimpa data. "
            "Gunakan --reset bila memang ingin membuat ulang database dummy."
        )
        return 1

    if not (DATA_DIR / "inventaris_dummy.csv").exists():
        from scripts.generate_dummy_data import generate
        for path in generate(DATA_DIR):
            print(f"Dibuat: {path}")

    inventory_data = (DATA_DIR / "inventaris_dummy.csv").read_bytes()
    preview = inventory_import_service.preview_inventory(
        inventory_data, "inventaris_dummy.csv", _mapping(INVENTORY_FIELDS), db_path=db_path
    )
    if preview.errors:
        print("Inventaris memiliki error:")
        for item in preview.errors[:10]:
            print(" -", item)
        return 1
    result = inventory_import_service.save_inventory_import(preview, db_path=db_path)
    print(f"Inventaris: {result['created']} server (batch #{result['batch_id']}).")

    scope_service.create_rule({
        "name": "Kecualikan environment dev",
        "dimension": "environment",
        "match_value": "dev",
        "reason": "Lingkungan pengembangan tidak termasuk scope rightsizing.",
        "active": True,
    }, db_path=db_path)

    batch_ids = {}
    ts_mapping = _mapping(TIMESERIES_FIELDS)
    for metric, filename in (("cpu", "cpu_dummy.csv"), ("memory", "memory_dummy.csv")):
        data = (DATA_DIR / filename).read_bytes()
        ts_preview = timeseries_import_service.preview_timeseries(
            data, filename, ts_mapping,
            metric=metric,
            timezone_name=TIMEZONE,
            interval_minutes=60,
            statistic_type="average",
            date_format="iso",
            decimal_format="dot",
            db_path=db_path,
        )
        if ts_preview.errors:
            print(f"{metric} memiliki error:")
            for item in ts_preview.errors[:10]:
                print(" -", item)
            return 1
        saved = timeseries_import_service.save_timeseries_import(ts_preview, db_path=db_path)
        batch_ids[metric] = saved["batch_id"]
        print(f"{metric}: {saved['created']} sampel (batch #{saved['batch_id']}).")

    tz = ZoneInfo(TIMEZONE)
    start = int(datetime(2026, 1, 1, 0, 0, tzinfo=tz).timestamp())
    end = int(datetime(2026, 1, 15, 0, 0, tzinfo=tz).timestamp())
    analysis = analyze(
        start, end, [batch_ids["cpu"]], [batch_ids["memory"]], DEFAULT_DISPLAY_TZ,
        db_path=db_path,
    )
    baseline_id = baseline_service.create_baseline(
        "Baseline dummy 14 hari pertama", analysis,
        notes="Dibuat oleh seed_dummy; semua angka fiktif.", db_path=db_path,
    )
    print(f"Baseline #{baseline_id}: {len(analysis.included_servers)} server dalam scope.")
    print("KPI sengaja tidak dibuat; modul tetap Belum Dikonfigurasi.")
    print(f"Database dummy siap: {db_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AppError as exc:
        print(f"Gagal seed: {exc}")
        raise SystemExit(1)
