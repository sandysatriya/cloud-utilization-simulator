def insert_samples(conn, batch_id: int, server_id: int, metric: str, rows) -> None:
    conn.executemany(
        "INSERT INTO utilization_sample(batch_id, server_id, metric, ts_utc, value) VALUES (?, ?, ?, ?, ?)",
        [(batch_id, server_id, metric, int(ts), float(value)) for ts, value in rows],
    )


def fetch_samples(conn, server_ids: list[int], metric: str, start_utc: int, end_utc: int,
                  batch_ids: list[int] | None = None):
    if not server_ids:
        return {}
    placeholders = ",".join("?" for _ in server_ids)
    params: list = [metric, *server_ids, start_utc, end_utc]
    batch_clause = ""
    if batch_ids is not None:
        if not batch_ids:
            return {}
        batch_placeholders = ",".join("?" for _ in batch_ids)
        batch_clause = f" AND batch_id IN ({batch_placeholders})"
        params.extend(batch_ids)
    rows = conn.execute(
        f"""SELECT server_id, ts_utc, value FROM utilization_sample
            WHERE metric = ? AND server_id IN ({placeholders})
              AND ts_utc >= ? AND ts_utc < ?{batch_clause}
            ORDER BY server_id, ts_utc""",
        params,
    ).fetchall()
    result: dict[int, list[tuple[int, float]]] = {}
    for row in rows:
        result.setdefault(row["server_id"], []).append((row["ts_utc"], row["value"]))
    return result


def existing_values(conn, server_ids: list[int], metric: str, start_utc: int, end_utc: int):
    data = fetch_samples(conn, server_ids, metric, start_utc, end_utc)
    return {
        (server_id, ts): value
        for server_id, rows in data.items()
        for ts, value in rows
    }


def count_samples(conn, batch_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM utilization_sample WHERE batch_id = ?", (batch_id,)
    ).fetchone()
    return int(row["c"])


def batch_range(conn, batch_id: int):
    row = conn.execute(
        "SELECT MIN(ts_utc) AS lo, MAX(ts_utc) AS hi FROM utilization_sample WHERE batch_id = ?",
        (batch_id,),
    ).fetchone()
    return row["lo"], row["hi"]


def data_server_ids(conn) -> set[int]:
    rows = conn.execute("SELECT DISTINCT server_id FROM utilization_sample").fetchall()
    return {r["server_id"] for r in rows}
