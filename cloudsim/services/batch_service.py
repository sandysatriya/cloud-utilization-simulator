from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import batches as batch_repo


def list_batches(data_type: str | None = None, db_path=None):
    with read_connection(db_path) as conn:
        return batch_repo.list_batches(conn, data_type)


def get_batch(batch_id: int, db_path=None):
    with read_connection(db_path) as conn:
        return batch_repo.get_batch(conn, batch_id)


def list_issues(batch_id: int, db_path=None) -> list[dict]:
    with read_connection(db_path) as conn:
        return batch_repo.list_issues(conn, batch_id)


def delete_batch(batch_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        batch_repo.delete_batch(conn, batch_id)
