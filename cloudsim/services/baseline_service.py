from cloudsim.analysis.baseline_compare import compare_baseline
from cloudsim.analysis.models import AnalysisResult
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import baselines as baseline_repo
from cloudsim.errors import NotFoundError, ValidationError


def create_baseline(name: str, analysis: AnalysisResult, notes: str | None = None, db_path=None) -> int:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValidationError("Nama baseline wajib diisi.")
    with transaction(db_path) as conn:
        return baseline_repo.create_baseline(conn, clean_name, analysis, notes)


def list_baselines(db_path=None) -> list[dict]:
    with read_connection(db_path) as conn:
        return baseline_repo.list_baselines(conn)


def get_baseline(baseline_id: int, db_path=None) -> dict:
    with read_connection(db_path) as conn:
        data = baseline_repo.get_baseline(conn, baseline_id)
    if data is None:
        raise NotFoundError("Baseline tidak ditemukan.")
    return data


def delete_baseline(baseline_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        baseline_repo.delete_baseline(conn, baseline_id)


def compare(baseline_id: int, analysis: AnalysisResult, db_path=None) -> dict:
    return compare_baseline(get_baseline(baseline_id, db_path), analysis)
