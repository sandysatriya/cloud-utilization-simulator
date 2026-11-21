from datetime import date

from cloudsim.analysis.models import Server
from cloudsim.clock import utc_now_iso
from cloudsim.enums import PRICE_UNITS, SCOPE_STATUS
from cloudsim.errors import NotFoundError, ValidationError


def row_to_server(row) -> Server:
    return Server(
        id=row["id"],
        code=row["server_code"],
        name=row["name"],
        environment=row["environment"],
        region=row["region"],
        workload=row["workload"],
        vcpu=row["vcpu"],
        ram_gib=row["ram_gib"],
        instance_type=row["instance_type"],
        scope_status=row["scope_status"],
        exclusion_reason=row["exclusion_reason"],
        price_amount=row["price_amount"],
        price_currency=row["price_currency"],
        price_unit=row["price_unit"],
        price_unit_label=row["price_unit_label"],
        price_source_date=row["price_source_date"],
        notes=row["notes"],
    )


def list_servers(conn) -> list[Server]:
    rows = conn.execute("SELECT * FROM server ORDER BY server_code COLLATE NOCASE").fetchall()
    return [row_to_server(r) for r in rows]


def get_server(conn, server_id: int | None = None, code: str | None = None) -> Server:
    if server_id is not None:
        row = conn.execute("SELECT * FROM server WHERE id = ?", (server_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM server WHERE server_code = ? COLLATE NOCASE", (code,)
        ).fetchone()
    if not row:
        raise NotFoundError("Server tidak ditemukan.")
    return row_to_server(row)


def existing_codes(conn) -> set[str]:
    rows = conn.execute("SELECT server_code FROM server").fetchall()
    return {r["server_code"].strip().lower() for r in rows}


def _normalize_price(data: dict) -> dict:
    amount = data.get("price_amount")
    if amount in (None, ""):
        return {
            "price_amount": None,
            "price_currency": None,
            "price_unit": None,
            "price_unit_label": None,
            "price_source_date": None,
        }
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Harga harus berupa angka.")
    if amount < 0:
        raise ValidationError("Harga tidak boleh negatif.")
    currency = str(data.get("price_currency") or "").strip().upper()
    unit = data.get("price_unit")
    label = (data.get("price_unit_label") or "").strip() or None
    source_date = data.get("price_source_date")
    if len(currency) != 3 or not currency.isalpha():
        raise ValidationError("Mata uang harus 3 huruf, contoh IDR atau USD.")
    if unit not in PRICE_UNITS:
        raise ValidationError("Satuan harga tidak valid.")
    if unit == "other" and not label:
        raise ValidationError("Satuan 'Lainnya' memerlukan label.")
    if not source_date:
        raise ValidationError("Tanggal sumber harga wajib diisi bila harga diisi.")
    try:
        date.fromisoformat(str(source_date))
    except ValueError:
        raise ValidationError("Tanggal sumber harga harus berformat YYYY-MM-DD.")
    return {
        "price_amount": amount,
        "price_currency": currency,
        "price_unit": unit,
        "price_unit_label": label if unit == "other" else None,
        "price_source_date": str(source_date),
    }


def validate_server_data(data: dict) -> dict:
    code = str(data.get("server_code") or "").strip()
    if not code:
        raise ValidationError("Kode server wajib diisi.")
    environment = str(data.get("environment") or "").strip()
    if not environment:
        raise ValidationError("Environment wajib diisi.")
    try:
        vcpu = int(data.get("vcpu"))
    except (TypeError, ValueError):
        raise ValidationError("vCPU harus bilangan bulat.")
    if vcpu <= 0:
        raise ValidationError("vCPU harus lebih besar dari 0.")
    try:
        ram = float(data.get("ram_gib"))
    except (TypeError, ValueError):
        raise ValidationError("RAM harus berupa angka.")
    if ram <= 0:
        raise ValidationError("RAM harus lebih besar dari 0.")
    scope = data.get("scope_status") or "in_scope"
    if scope not in SCOPE_STATUS:
        raise ValidationError("Status scope tidak valid.")
    reason = (data.get("exclusion_reason") or "").strip() or None
    if scope == "excluded" and not reason:
        raise ValidationError("Server yang dikecualikan wajib memiliki alasan.")
    price = _normalize_price(data)
    return {
        "server_code": code,
        "name": (data.get("name") or "").strip() or None,
        "environment": environment,
        "region": (data.get("region") or "").strip() or None,
        "workload": (data.get("workload") or "").strip() or None,
        "vcpu": vcpu,
        "ram_gib": ram,
        "instance_type": (data.get("instance_type") or "").strip() or None,
        "scope_status": scope,
        "exclusion_reason": reason if scope == "excluded" else None,
        "notes": (data.get("notes") or "").strip() or None,
        **price,
    }


def create_server(conn, data: dict) -> int:
    clean = validate_server_data(data)
    now = utc_now_iso()
    try:
        cur = conn.execute(
            """
            INSERT INTO server(server_code, name, environment, region, workload, vcpu, ram_gib,
                               instance_type, scope_status, exclusion_reason, price_amount,
                               price_currency, price_unit, price_unit_label, price_source_date,
                               notes, created_at, updated_at)
            VALUES (:server_code, :name, :environment, :region, :workload, :vcpu, :ram_gib,
                    :instance_type, :scope_status, :exclusion_reason, :price_amount,
                    :price_currency, :price_unit, :price_unit_label, :price_source_date,
                    :notes, :created_at, :updated_at)
            """,
            {**clean, "created_at": now, "updated_at": now},
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValidationError(f"Kode server '{clean['server_code']}' sudah ada.")
        raise
    return int(cur.lastrowid)


def update_server(conn, server_id: int, data: dict) -> None:
    clean = validate_server_data(data)
    try:
        conn.execute(
            """
            UPDATE server SET server_code=:server_code, name=:name, environment=:environment,
                region=:region, workload=:workload, vcpu=:vcpu, ram_gib=:ram_gib,
                instance_type=:instance_type, scope_status=:scope_status,
                exclusion_reason=:exclusion_reason, price_amount=:price_amount,
                price_currency=:price_currency, price_unit=:price_unit,
                price_unit_label=:price_unit_label, price_source_date=:price_source_date,
                notes=:notes, updated_at=:updated_at
            WHERE id=:id
            """,
            {**clean, "id": server_id, "updated_at": utc_now_iso()},
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValidationError(f"Kode server '{clean['server_code']}' sudah ada.")
        raise


def delete_server(conn, server_id: int) -> None:
    sample = conn.execute(
        "SELECT 1 FROM utilization_sample WHERE server_id = ? LIMIT 1", (server_id,)
    ).fetchone()
    if sample:
        raise ValidationError(
            "Server memiliki data time series dan tidak dapat dihapus. "
            "Gunakan status Dikecualikan agar tetap tercatat."
        )
    conn.execute("DELETE FROM server WHERE id = ?", (server_id,))
