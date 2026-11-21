from cloudsim.analysis.scope import effective_exclusions, _rule_value
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import scope_rules as rule_repo
from cloudsim.db.repositories import servers as server_repo


def list_rules(db_path=None) -> list[dict]:
    with read_connection(db_path) as conn:
        return rule_repo.list_rules(conn)


def create_rule(data: dict, db_path=None) -> int:
    with transaction(db_path) as conn:
        return rule_repo.create_rule(conn, data)


def update_rule(rule_id: int, data: dict, db_path=None) -> None:
    with transaction(db_path) as conn:
        rule_repo.update_rule(conn, rule_id, data)


def delete_rule(rule_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        rule_repo.delete_rule(conn, rule_id)


def effective_exclusions_list(db_path=None):
    with read_connection(db_path) as conn:
        return effective_exclusions(server_repo.list_servers(conn), rule_repo.list_rules(conn))


def affected_servers(rule: dict, db_path=None) -> list[str]:
    with read_connection(db_path) as conn:
        servers = server_repo.list_servers(conn)
    value = str(rule.get("match_value") or "").strip().lower()
    if not rule.get("dimension") or not value:
        return []
    return [
        s.code for s in servers
        if (_rule_value(s, rule["dimension"]) or "").strip().lower() == value
    ]
