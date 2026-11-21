import pytest

from cloudsim.config import SETTING_DEFAULTS
from cloudsim.db.connection import read_connection
from cloudsim.db.migrate import migrate
from cloudsim.errors import AppError, ValidationError
from cloudsim.services import (
    batch_service,
    inventory_service,
    settings_service,
)


def test_migration_is_idempotent_and_keeps_settings(db_path):
    settings_service.update_thresholds(75, 60, 12, "Asia/Jakarta", db_path=db_path)
    migrate(db_path)
    values = settings_service.get_settings(db_path=db_path)
    assert values == {
        "display_timezone": "Asia/Jakarta",
        "warning_threshold_pct": 75.0,
        "min_completeness_pct": 60.0,
        "min_samples": 12,
    }
    with read_connection(db_path) as conn:
        version = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        settings_count = conn.execute("SELECT COUNT(*) AS c FROM app_setting").fetchone()["c"]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert version == 1
    assert settings_count == len(SETTING_DEFAULTS)
    assert fk == 1


def test_newer_database_version_is_refused(tmp_path):
    path = tmp_path / "future.db"
    migrate(path)
    with read_connection(path) as conn:
        conn.execute("UPDATE schema_version SET version = 99")
        conn.commit()
    with pytest.raises(AppError, match="lebih baru"):
        migrate(path)


@pytest.mark.parametrize("values", [
    (0, 80, 24),
    (101, 80, 24),
    (80, -1, 24),
    (80, 101, 24),
    (80, 80, 0),
])
def test_invalid_thresholds_are_rejected(db_path, values):
    with pytest.raises(ValidationError):
        settings_service.update_thresholds(*values, db_path=db_path)


def test_invalid_timezone_is_rejected(db_path):
    with pytest.raises(ValidationError, match="Zona waktu"):
        settings_service.update_thresholds(80, 80, 24, "Mars/Olympus", db_path=db_path)


def test_server_with_samples_cannot_be_deleted(dataset):
    server = next(
        s for s in inventory_service.list_servers(db_path=dataset.db_path)
        if s.code == "SRV-A"
    )
    with pytest.raises(ValidationError, match="time series"):
        inventory_service.delete_server(server.id, db_path=dataset.db_path)

    batch_service.delete_batch(dataset.cpu_batch, db_path=dataset.db_path)
    batch_service.delete_batch(dataset.memory_batch, db_path=dataset.db_path)
    inventory_service.delete_server(server.id, db_path=dataset.db_path)
    codes = {s.code for s in inventory_service.list_servers(db_path=dataset.db_path)}
    assert "SRV-A" not in codes
