from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import servers as server_repo
from cloudsim.errors import NotFoundError


def list_servers(db_path=None):
    with read_connection(db_path) as conn:
        return server_repo.list_servers(conn)


def get_server(server_id: int, db_path=None):
    with read_connection(db_path) as conn:
        return server_repo.get_server(conn, server_id=server_id)


def create_server(data: dict, db_path=None) -> int:
    with transaction(db_path) as conn:
        return server_repo.create_server(conn, data)


def update_server(server_id: int, data: dict, db_path=None) -> None:
    with transaction(db_path) as conn:
        server_repo.update_server(conn, server_id, data)


def delete_server(server_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        server_repo.delete_server(conn, server_id)


def find_server(code: str):
    with read_connection() as conn:
        row = conn.execute(
            "SELECT * FROM server WHERE server_code = ? COLLATE NOCASE", (code,)
        ).fetchone()
        if not row:
            raise NotFoundError("Server tidak ditemukan.")
        return server_repo.row_to_server(row)
