from cloudsim.errors import ValidationError

INVENTORY_FIELDS = [
    {"key": "server_code", "label": "ID server", "required": True},
    {"key": "name", "label": "Nama/alias", "required": False},
    {"key": "environment", "label": "Environment", "required": True},
    {"key": "region", "label": "Region", "required": False},
    {"key": "workload", "label": "Workload", "required": False},
    {"key": "vcpu", "label": "vCPU", "required": True},
    {"key": "ram_gib", "label": "RAM GiB", "required": True},
    {"key": "instance_type", "label": "Tipe instance", "required": False},
    {"key": "scope_status", "label": "Status scope", "required": False},
    {"key": "exclusion_reason", "label": "Alasan pengecualian", "required": False},
    {"key": "price_amount", "label": "Harga", "required": False},
    {"key": "price_currency", "label": "Mata uang", "required": False},
    {"key": "price_unit", "label": "Satuan harga", "required": False},
    {"key": "price_unit_label", "label": "Label satuan lainnya", "required": False},
    {"key": "price_source_date", "label": "Tanggal sumber harga", "required": False},
    {"key": "notes", "label": "Catatan", "required": False},
]

TIMESERIES_FIELDS = [
    {"key": "server_code", "label": "ID server", "required": True},
    {"key": "timestamp", "label": "Timestamp", "required": True},
    {"key": "value", "label": "Nilai utilization (%)", "required": True},
]


def validate_mapping(mapping: dict[str, str], fields: list[dict]) -> None:
    for field in fields:
        if field["required"] and not mapping.get(field["key"]):
            raise ValidationError(f"Kolom wajib belum dipetakan: {field['label']}.")
    selected = [str(v).strip().lower() for v in mapping.values() if v]
    if len(selected) != len(set(selected)):
        raise ValidationError("Satu kolom sumber tidak boleh dipetakan ke lebih dari satu target.")


def apply_mapping(df, mapping: dict[str, str]):
    output = {}
    for target, source in mapping.items():
        if not source:
            continue
        if source not in df.columns:
            raise ValidationError(f"Kolom sumber '{source}' tidak ditemukan.")
        output[target] = df[source]
    return type(df)(output)
