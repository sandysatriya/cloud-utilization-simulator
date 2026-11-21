from cloudsim.analysis.completeness import preview_completeness_pct
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import batches as batch_repo
from cloudsim.db.repositories import samples as sample_repo
from cloudsim.db.repositories import servers as server_repo
from cloudsim.enums import STATISTIC_TYPES
from cloudsim.errors import ImportBlocked, ValidationError
from cloudsim.io.column_mapping import TIMESERIES_FIELDS, apply_mapping, validate_mapping
from cloudsim.io.parsers import (
    clean_text, is_blank, parse_datetime_utc, parse_number, validate_timezone,
)
from cloudsim.io.readers import read_table
from cloudsim.services.import_common import ImportPreview, issue, sha256_bytes


def preview_timeseries(
    data: bytes,
    filename: str,
    mapping: dict,
    *,
    metric: str,
    timezone_name: str,
    interval_minutes: float | None,
    statistic_type: str,
    statistic_label: str | None = None,
    date_format: str = "iso",
    decimal_format: str = "dot",
    sheet: str | None = None,
    delimiter: str = ",",
    header_row: int = 1,
    db_path=None,
) -> ImportPreview:
    validate_mapping(mapping, TIMESERIES_FIELDS)
    if metric not in {"cpu", "memory"}:
        raise ValidationError("Metrik harus CPU atau memory.")
    validate_timezone(timezone_name)
    if statistic_type not in STATISTIC_TYPES:
        raise ValidationError("Jenis statistik tidak valid.")
    statistic_label = (statistic_label or "").strip() or None
    if statistic_type == "other" and not statistic_label:
        raise ValidationError("Jenis statistik 'Lainnya' memerlukan label.")
    if interval_minutes is not None and interval_minutes < 0:
        raise ValidationError("Interval tidak boleh negatif.")
    interval_seconds = int(round(interval_minutes * 60)) if interval_minutes else None
    if interval_seconds is not None and interval_seconds <= 0:
        interval_seconds = None

    df = read_table(data, filename, sheet=sheet, delimiter=delimiter, header_row=header_row)
    mapped = apply_mapping(df, mapping)
    file_hash = sha256_bytes(data)

    errors: list[dict] = []
    warnings: list[dict] = []
    parsed: list[dict] = []

    with read_connection(db_path) as conn:
        servers = server_repo.list_servers(conn)
        prior = batch_repo.find_batch_by_hash(conn, file_hash)
        server_by_code = {s.code.strip().lower(): s for s in servers}
    if prior:
        warnings.append(issue(
            "warning", "W_FILE_HASH", "",
            f"File dengan hash yang sama pernah diimpor sebagai batch #{prior['id']} ({prior['file_name']}).",
        ))

    for position, (_, row) in enumerate(mapped.iterrows()):
        row_number = header_row + 1 + position
        raw = row.to_dict()
        try:
            code = clean_text(raw.get("server_code"))
            if not code:
                raise ValidationError("ID server kosong.")
            server = server_by_code.get(code.lower())
            if not server:
                raise ValidationError(f"ID server '{code}' belum ada di inventaris.")
            ts_utc = parse_datetime_utc(raw.get("timestamp"), date_format, timezone_name)
            value = parse_number(raw.get("value"), decimal_format)
            if value < 0 or value > 100:
                raise ValidationError(f"Nilai {value} di luar rentang 0–100.")
            parsed.append({
                "row": row_number,
                "server": server,
                "server_id": server.id,
                "server_code": server.code,
                "ts_utc": ts_utc,
                "value": value,
            })
        except ValidationError as exc:
            errors.append(issue("error", "E_ROW", row_number, str(exc)))

    groups: dict[tuple[int, int], list[dict]] = {}
    for record in parsed:
        groups.setdefault((record["server_id"], record["ts_utc"]), []).append(record)

    candidates: list[dict] = []
    for group in groups.values():
        if len(group) == 1:
            candidates.append(group[0])
            continue
        distinct = {round(record["value"], 9) for record in group}
        if len(distinct) == 1:
            candidates.append(group[0])
            for duplicate in group[1:]:
                warnings.append(issue(
                    "warning", "W_DUP_FILE_IDENTICAL", duplicate["row"],
                    "Duplikat identik di dalam file; baris ini dilewati, nilai tidak dipilih diam-diam.",
                ))
        else:
            for record in group:
                errors.append(issue(
                    "error", "E_DUP_FILE_CONFLICT", record["row"],
                    "Konflik duplikat di dalam file (server+timestamp sama, nilai berbeda); "
                    "semua baris konflik tidak diimpor.",
                ))

    if candidates:
        min_ts = min(record["ts_utc"] for record in candidates)
        max_ts = max(record["ts_utc"] for record in candidates)
        server_ids = sorted({record["server_id"] for record in candidates})
        with read_connection(db_path) as conn:
            existing = sample_repo.existing_values(
                conn, server_ids, metric, min_ts, max_ts + 1
            )
    else:
        existing = {}

    accepted: list[dict] = []
    for record in candidates:
        key = (record["server_id"], record["ts_utc"])
        if key in existing:
            if round(existing[key], 9) == round(record["value"], 9):
                warnings.append(issue(
                    "warning", "W_DUP_DB_IDENTICAL", record["row"],
                    "Data identik sudah ada di database; baris dilewati dan tidak ditimpa.",
                ))
            else:
                errors.append(issue(
                    "error", "E_DUP_DB_CONFLICT", record["row"],
                    f"Konflik dengan data tersimpan (nilai lama {existing[key]}); "
                    "data lama tidak ditimpa.",
                ))
            continue
        if interval_seconds and record["ts_utc"] % interval_seconds != 0:
            warnings.append(issue(
                "warning", "W_TIMESTAMP_ALIGN", record["row"],
                f"Timestamp tidak selaras dengan grid interval {interval_seconds} detik.",
            ))
        accepted.append(record)

    accepted.sort(key=lambda item: (item["server_id"], item["ts_utc"]))
    summary = []
    by_server: dict[str, list[dict]] = {}
    for record in accepted:
        by_server.setdefault(record["server_code"], []).append(record)
    for code, rows in sorted(by_server.items()):
        rows.sort(key=lambda item: item["ts_utc"])
        first_ts = rows[0]["ts_utc"]
        last_ts = rows[-1]["ts_utc"]
        summary.append({
            "ID server": code,
            "Jumlah sampel": len(rows),
            "Rentang awal": first_ts,
            "Rentang akhir": last_ts,
            "Kelengkapan (%)": preview_completeness_pct(
                len(rows), first_ts, last_ts, interval_seconds
            ),
        })

    period_start = min((r["ts_utc"] for r in accepted), default=None)
    period_end = max((r["ts_utc"] for r in accepted), default=None)
    return ImportPreview(
        kind=metric,
        file_name=filename,
        file_sha256=file_hash,
        total_rows=len(mapped),
        accepted_count=len(accepted),
        accepted_rows=accepted,
        errors=errors,
        warnings=warnings,
        metadata={
            "metric": metric,
            "timezone": timezone_name,
            "interval_seconds": interval_seconds,
            "statistic_type": statistic_type,
            "statistic_label": statistic_label,
            "date_format": date_format,
            "decimal_format": decimal_format,
        },
        server_summary=summary,
        period_start_utc=period_start,
        period_end_utc=period_end,
    )


def save_timeseries_import(preview: ImportPreview, *, allow_partial: bool = False,
                           db_path=None, notes: str | None = None) -> dict:
    if preview.errors and not allow_partial:
        raise ImportBlocked(
            "Import diblokir karena masih ada baris bermasalah. Perbaiki file atau pilih "
            "simpan hanya baris valid secara eksplisit."
        )
    if not preview.accepted_rows:
        raise ImportBlocked("Tidak ada baris valid untuk disimpan.")
    meta = preview.metadata
    with transaction(db_path) as conn:
        batch_id = batch_repo.create_batch(
            conn,
            data_type=meta["metric"],
            file_name=preview.file_name,
            file_sha256=preview.file_sha256,
            timezone=meta["timezone"],
            interval_seconds=meta["interval_seconds"],
            statistic_type=meta["statistic_type"],
            statistic_label=meta["statistic_label"],
            period_start_utc=preview.period_start_utc,
            period_end_utc=preview.period_end_utc,
            total_rows=preview.total_rows,
            accepted_rows=len(preview.accepted_rows),
            rejected_rows=preview.total_rows - len(preview.accepted_rows),
            notes=notes,
        )
        batch_repo.add_issues(conn, batch_id, preview.errors + preview.warnings)
        by_server: dict[int, list[tuple[int, float]]] = {}
        for record in preview.accepted_rows:
            by_server.setdefault(record["server_id"], []).append(
                (record["ts_utc"], record["value"])
            )
        for server_id, rows in by_server.items():
            sample_repo.insert_samples(conn, batch_id, server_id, meta["metric"], rows)
    return {
        "batch_id": batch_id,
        "created": len(preview.accepted_rows),
        "skipped": preview.total_rows - len(preview.accepted_rows),
    }
