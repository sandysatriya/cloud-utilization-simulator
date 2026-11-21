import csv
import io
import itertools
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from cloudsim.services import inventory_service, timeseries_import_service

START = int(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp())
END = START + 4 * 3600
HOUR = 3600

INVENTORY_HEADERS = [
    "server_code", "name", "environment", "region", "workload", "vcpu", "ram_gib",
    "instance_type", "scope_status", "exclusion_reason", "price_amount", "price_currency",
    "price_unit", "price_unit_label", "price_source_date", "notes",
]
TS_HEADERS = ["server_code", "timestamp", "value"]
TS_MAPPING = {"server_code": "server_code", "timestamp": "timestamp", "value": "value"}
INVENTORY_MAPPING = {name: name for name in INVENTORY_HEADERS}

_counter = itertools.count(1)


def csv_bytes(headers: list[str], rows: list[dict] | list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        if isinstance(row, dict):
            writer.writerow([row.get(header, "") for header in headers])
        else:
            writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def server_data(code: str, **overrides) -> dict:
    data = {
        "server_code": code,
        "name": f"Server {code}",
        "environment": "production",
        "region": "id-jkt",
        "workload": "web",
        "vcpu": 4,
        "ram_gib": 8.0,
        "instance_type": None,
        "scope_status": "in_scope",
        "exclusion_reason": None,
        "notes": None,
    }
    data.update(overrides)
    return data


def add_server(db_path, code: str, **overrides) -> int:
    return inventory_service.create_server(server_data(code, **overrides), db_path=db_path)


def series(start: int, values: list[float], interval: int = HOUR) -> list[tuple[int, float]]:
    return [(start + index * interval, float(value)) for index, value in enumerate(values)]


def _local_text(ts: int, timezone_name: str) -> str:
    return datetime.fromtimestamp(ts, ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")


def add_time_batch(
    db_path,
    metric: str,
    samples: dict[str, list[tuple[int, float]]],
    *,
    timezone_name: str = "UTC",
    interval_minutes: float | None = 60,
    statistic_type: str = "average",
    statistic_label: str | None = None,
    filename: str | None = None,
    allow_partial: bool = False,
) -> tuple[int, object]:
    rows = []
    for code, values in samples.items():
        for ts, value in values:
            rows.append([code, _local_text(ts, timezone_name), value])
    data = csv_bytes(TS_HEADERS, rows)
    filename = filename or f"{metric}_{statistic_type}_{next(_counter)}.csv"
    preview = timeseries_import_service.preview_timeseries(
        data, filename, TS_MAPPING,
        metric=metric,
        timezone_name=timezone_name,
        interval_minutes=interval_minutes,
        statistic_type=statistic_type,
        statistic_label=statistic_label,
        db_path=db_path,
    )
    if preview.errors and not allow_partial:
        raise AssertionError(f"Unexpected preview errors: {preview.errors}")
    saved = timeseries_import_service.save_timeseries_import(
        preview, allow_partial=allow_partial, db_path=db_path
    )
    return saved["batch_id"], preview


def preview_ts(
    db_path,
    metric: str,
    rows: list[dict] | list[list],
    *,
    timezone_name: str = "UTC",
    interval_minutes: float | None = 60,
    statistic_type: str = "average",
    statistic_label: str | None = None,
    filename: str | None = None,
):
    data = csv_bytes(TS_HEADERS, rows)
    return timeseries_import_service.preview_timeseries(
        data, filename or f"{metric}_preview.csv", TS_MAPPING,
        metric=metric,
        timezone_name=timezone_name,
        interval_minutes=interval_minutes,
        statistic_type=statistic_type,
        statistic_label=statistic_label,
        db_path=db_path,
    )
