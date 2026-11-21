from collections import Counter

from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import batches as batch_repo
from cloudsim.db.repositories import servers as server_repo
from cloudsim.errors import ImportBlocked, ValidationError
from cloudsim.io.column_mapping import INVENTORY_FIELDS, apply_mapping, validate_mapping
from cloudsim.io.parsers import (
    clean_text, is_blank, parse_currency, parse_date_value, parse_number,
    parse_price_unit, parse_scope_status,
)
from cloudsim.io.readers import read_table
from cloudsim.services.import_common import ImportPreview, issue, sha256_bytes


def _parse_inventory_row(raw: dict) -> dict:
    code = clean_text(raw.get("server_code"))
    if not code:
        raise ValidationError("ID server kosong.")
    environment = clean_text(raw.get("environment"))
    if not environment:
        raise ValidationError("Environment kosong.")

    if is_blank(raw.get("vcpu")):
        raise ValidationError("vCPU kosong; nilai kosong tidak dianggap 0.")
    vcpu_number = parse_number(raw.get("vcpu"))
    if not vcpu_number.is_integer():
        raise ValidationError("vCPU harus bilangan bulat.")
    vcpu = int(vcpu_number)
    if is_blank(raw.get("ram_gib")):
        raise ValidationError("RAM kosong; nilai kosong tidak dianggap 0.")
    ram_gib = parse_number(raw.get("ram_gib"))

    scope_status = parse_scope_status(raw.get("scope_status"))
    exclusion_reason = clean_text(raw.get("exclusion_reason"))
    if scope_status == "excluded" and not exclusion_reason:
        raise ValidationError("Server dikecualikan tetapi alasan kosong.")

    price_related = [
        raw.get("price_amount"), raw.get("price_currency"), raw.get("price_unit"),
        raw.get("price_unit_label"), raw.get("price_source_date"),
    ]
    price_amount = None
    if not is_blank(raw.get("price_amount")):
        price_amount = parse_number(raw.get("price_amount"))
    elif any(not is_blank(value) for value in price_related):
        raise ValidationError("Harga diisi sebagian; lengkapi atau kosongkan semua field harga.")

    price_currency = parse_currency(raw.get("price_currency"))
    price_unit = parse_price_unit(raw.get("price_unit"))
    price_unit_label = clean_text(raw.get("price_unit_label")) or None
    price_source_date = None
    if not is_blank(raw.get("price_source_date")):
        price_source_date = parse_date_value(raw.get("price_source_date"), "iso").isoformat()

    payload = {
        "server_code": code,
        "name": clean_text(raw.get("name")),
        "environment": environment,
        "region": clean_text(raw.get("region")),
        "workload": clean_text(raw.get("workload")),
        "vcpu": vcpu,
        "ram_gib": ram_gib,
        "instance_type": clean_text(raw.get("instance_type")),
        "scope_status": scope_status,
        "exclusion_reason": exclusion_reason,
        "price_amount": price_amount,
        "price_currency": price_currency,
        "price_unit": price_unit,
        "price_unit_label": price_unit_label,
        "price_source_date": price_source_date,
        "notes": clean_text(raw.get("notes")),
    }
    return server_repo.validate_server_data(payload)


def preview_inventory(
    data: bytes,
    filename: str,
    mapping: dict,
    *,
    sheet: str | None = None,
    delimiter: str = ",",
    header_row: int = 1,
    db_path=None,
) -> ImportPreview:
    validate_mapping(mapping, INVENTORY_FIELDS)
    df = read_table(data, filename, sheet=sheet, delimiter=delimiter, header_row=header_row)
    mapped = apply_mapping(df, mapping)
    file_hash = sha256_bytes(data)

    errors: list[dict] = []
    warnings: list[dict] = []
    accepted: list[dict] = []
    with read_connection(db_path) as conn:
        existing = server_repo.existing_codes(conn)
        prior = batch_repo.find_batch_by_hash(conn, file_hash)
    if prior:
        warnings.append(issue(
            "warning", "W_FILE_HASH", "",
            f"File dengan hash yang sama pernah diimpor sebagai batch #{prior['id']} ({prior['file_name']}).",
        ))

    codes = [clean_text(row.get("server_code")).lower() for _, row in mapped.iterrows()]
    counts = Counter(code for code in codes if code)
    for code, count in counts.items():
        if count > 1:
            errors.append(issue(
                "error", "E_DUP_FILE", "",
                f"ID server '{code}' muncul {count} kali dalam file; tidak ada baris yang dipilih diam-diam.",
            ))

    for position, (_, row) in enumerate(mapped.iterrows()):
        row_number = header_row + 1 + position
        raw = row.to_dict()
        code = clean_text(raw.get("server_code"))
        try:
            parsed = _parse_inventory_row(raw)
            if code and counts.get(code.lower(), 0) > 1:
                raise ValidationError(f"ID server '{code}' duplikat di dalam file.")
            if code and code.lower() in existing:
                raise ValidationError(f"ID server '{code}' sudah ada di database; tidak ditimpa.")
            accepted.append(parsed)
        except ValidationError as exc:
            errors.append(issue("error", "E_ROW", row_number, str(exc)))

    return ImportPreview(
        kind="inventory",
        file_name=filename,
        file_sha256=file_hash,
        total_rows=len(mapped),
        accepted_count=len(accepted),
        accepted_rows=accepted,
        errors=errors,
        warnings=warnings,
        metadata={},
    )


def save_inventory_import(preview: ImportPreview, *, allow_partial: bool = False, db_path=None,
                          notes: str | None = None) -> dict:
    if preview.errors and not allow_partial:
        raise ImportBlocked(
            "Import diblokir karena masih ada baris bermasalah. Perbaiki file atau pilih "
            "simpan hanya baris valid secara eksplisit."
        )
    if not preview.accepted_rows:
        raise ImportBlocked("Tidak ada baris valid untuk disimpan.")

    with transaction(db_path) as conn:
        batch_id = batch_repo.create_batch(
            conn,
            data_type="inventory",
            file_name=preview.file_name,
            file_sha256=preview.file_sha256,
            total_rows=preview.total_rows,
            accepted_rows=len(preview.accepted_rows),
            rejected_rows=preview.total_rows - len(preview.accepted_rows),
            notes=notes,
        )
        batch_repo.add_issues(conn, batch_id, preview.errors + preview.warnings)
        for row in preview.accepted_rows:
            server_repo.create_server(conn, row)
    return {
        "batch_id": batch_id,
        "created": len(preview.accepted_rows),
        "skipped": preview.total_rows - len(preview.accepted_rows),
    }
