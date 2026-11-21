from pathlib import Path

import pandas as pd

from cloudsim.io.column_mapping import INVENTORY_FIELDS
from cloudsim.io.excel_writer import workbook_bytes

INVENTORY_HEADERS = [field["label"] for field in INVENTORY_FIELDS]

INSTRUCTIONS = [
    ["Template Inventaris Server"],
    ["Semua data contoh adalah dummy. Jangan memasukkan kredensial cloud."],
    ["Isi satu baris per server. Header jangan diubah."],
    ["Kolom wajib: ID server, Environment, vCPU, RAM GiB."],
    ["vCPU dan RAM GiB harus angka > 0."],
    ["Status scope: in_scope atau excluded. Server excluded wajib memiliki alasan."],
    ["Harga opsional; jika diisi lengkapi harga, mata uang (3 huruf), satuan, dan tanggal sumber (YYYY-MM-DD)."],
    ["Satuan harga: per_hour, per_month, per_vcpu_hour, per_gib_month, other."],
    ["Harga tidak dikonversi dan tidak dianggap proporsional terhadap ukuran instance."],
]


def inventory_template_bytes() -> bytes:
    inventory = pd.DataFrame(columns=INVENTORY_HEADERS)
    instructions = pd.DataFrame({"Petunjuk": [row[0] for row in INSTRUCTIONS]})
    return workbook_bytes([("Petunjuk", instructions), ("Inventaris", inventory)])


def timeseries_template_csv_bytes() -> bytes:
    return "ID server,Timestamp,Nilai utilization (%)\n".encode("utf-8")


def write_templates(target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = target_dir / "inventaris_v1.xlsx"
    timeseries_path = target_dir / "time_series_v1.csv"
    inventory_path.write_bytes(inventory_template_bytes())
    timeseries_path.write_bytes(timeseries_template_csv_bytes())
    return [inventory_path, timeseries_path]
