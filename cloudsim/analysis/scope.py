from cloudsim.analysis.models import Exclusion, Server


def _rule_value(server: Server, dimension: str) -> str | None:
    if dimension == "environment":
        return server.environment
    if dimension == "workload":
        return server.workload
    if dimension == "region":
        return server.region
    if dimension == "server":
        return server.code
    return None


def effective_exclusions(servers: list[Server], rules: list[dict]) -> list[Exclusion]:
    exclusions: list[Exclusion] = []
    active_rules = [r for r in rules if int(r.get("active", 1)) == 1]
    for server in servers:
        if server.scope_status == "excluded" and (server.exclusion_reason or "").strip():
            exclusions.append(Exclusion(
                server_code=server.code,
                server_name=server.name,
                source="manual",
                rule_name=None,
                reason=server.exclusion_reason.strip(),
            ))
        for rule in active_rules:
            value = _rule_value(server, rule["dimension"])
            if value is None:
                continue
            if value.strip().lower() == str(rule["match_value"]).strip().lower():
                exclusions.append(Exclusion(
                    server_code=server.code,
                    server_name=server.name,
                    source="rule",
                    rule_name=rule["name"],
                    reason=rule["reason"],
                ))
    return exclusions


def excluded_codes(exclusions: list[Exclusion]) -> set[str]:
    return {e.server_code for e in exclusions}
