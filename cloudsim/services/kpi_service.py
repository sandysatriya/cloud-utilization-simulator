import sqlite3

from cloudsim.analysis.kpi import validate_definition, validate_thresholds
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import kpi as kpi_repo
from cloudsim.errors import NotFoundError, ValidationError


def list_definitions(db_path=None) -> list[dict]:
    with read_connection(db_path) as conn:
        return kpi_repo.list_definitions(conn)


def get_definition(kpi_id: int, db_path=None) -> dict:
    with read_connection(db_path) as conn:
        data = kpi_repo.get_definition(conn, kpi_id)
    if data is None:
        raise NotFoundError("Definisi KPI tidak ditemukan.")
    return data


def save_definition(definition: dict, thresholds: list[dict] | None = None,
                    kpi_id: int | None = None, approve: bool = False, db_path=None) -> int:
    if not str(definition.get("name") or "").strip():
        raise ValidationError("Nama KPI wajib diisi.")
    if definition.get("scope_mode") == "baseline_scope" and not definition.get("baseline_id"):
        raise ValidationError("Mode scope baseline memerlukan baseline yang dipilih.")
    if definition.get("operator") == "between" and definition.get("target_value_upper") is None:
        raise ValidationError("Operator 'between' memerlukan batas atas.")
    upper = definition.get("target_value_upper")
    target = definition.get("target_value")
    if upper is not None and target is not None and upper < target:
        raise ValidationError("Batas atas KPI tidak boleh lebih kecil dari target.")
    with transaction(db_path) as conn:
        existing = kpi_repo.get_definition(conn, kpi_id) if kpi_id is not None else None
        if kpi_id is not None and existing is None:
            raise NotFoundError("Definisi KPI tidak ditemukan.")
        if approve:
            validate_definition(definition, approve=True)
            effective = thresholds if thresholds is not None else (existing or {}).get("thresholds", [])
            validate_thresholds(effective or [])
        elif thresholds is not None:
            validate_thresholds(thresholds)
        try:
            return kpi_repo.save_definition(conn, definition, thresholds, kpi_id, approve)
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"Definisi KPI melanggar aturan data: {exc}")


def approve_definition(kpi_id: int, db_path=None) -> int:
    definition = get_definition(kpi_id, db_path)
    payload = dict(definition)
    payload["thresholds"] = definition.get("thresholds") or []
    return save_definition(payload, None, kpi_id, approve=True, db_path=db_path)


def revoke_definition(kpi_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        if kpi_repo.get_definition(conn, kpi_id) is None:
            raise NotFoundError("Definisi KPI tidak ditemukan.")
        kpi_repo.revoke_definition(conn, kpi_id)


def delete_definition(kpi_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        kpi_repo.delete_definition(conn, kpi_id)

