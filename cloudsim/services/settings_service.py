from cloudsim.config import (
    DEFAULT_DISPLAY_TZ,
    DEFAULT_MIN_COMPLETENESS,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_WARNING_THRESHOLD,
)
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import settings as settings_repo
from cloudsim.errors import ValidationError
from cloudsim.io.parsers import validate_timezone


def get_settings(db_path=None) -> dict:
    with read_connection(db_path) as conn:
        values = settings_repo.get_settings(conn)
    return {
        "display_timezone": values.get("display_timezone", DEFAULT_DISPLAY_TZ),
        "warning_threshold_pct": float(values.get("warning_threshold_pct", DEFAULT_WARNING_THRESHOLD)),
        "min_completeness_pct": float(values.get("min_completeness_pct", DEFAULT_MIN_COMPLETENESS)),
        "min_samples": int(values.get("min_samples", DEFAULT_MIN_SAMPLES)),
    }


def update_thresholds(
    warning_threshold_pct: float,
    min_completeness_pct: float,
    min_samples: int,
    display_timezone: str | None = None,
    db_path=None,
) -> None:
    if not (0 < float(warning_threshold_pct) <= 100):
        raise ValidationError("Ambang peringatan harus lebih dari 0 dan maksimal 100.")
    if not (0 <= float(min_completeness_pct) <= 100):
        raise ValidationError("Kelengkapan minimum harus di antara 0 dan 100.")
    if int(min_samples) < 1:
        raise ValidationError("Jumlah sampel minimum minimal 1.")
    if display_timezone:
        validate_timezone(display_timezone)
    with transaction(db_path) as conn:
        settings_repo.set_setting(conn, "warning_threshold_pct", warning_threshold_pct)
        settings_repo.set_setting(conn, "min_completeness_pct", min_completeness_pct)
        settings_repo.set_setting(conn, "min_samples", int(min_samples))
        if display_timezone:
            settings_repo.set_setting(conn, "display_timezone", display_timezone)
