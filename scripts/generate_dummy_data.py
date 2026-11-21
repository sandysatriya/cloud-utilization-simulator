"""Buat dataset dummy deterministik. Tidak dijalankan otomatis oleh aplikasi."""

import argparse
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "dummy_data"

SERVERS = [
    # code, name, env, region, workload, vcpu, ram, instance, scope, reason, price
    ("SRV-WEB-01", "web-frontend-1", "production", "jakarta", "web", 4, 8, "dummy-gp-2x4", "", "", 1850000),
    ("SRV-WEB-02", "web-frontend-2", "production", "jakarta", "web", 4, 8, "dummy-gp-2x4", "", "", 1850000),
    ("SRV-API-01", "api-gateway-1", "production", "jakarta", "api", 8, 16, "dummy-gp-4x8", "", "", 3600000),
    ("SRV-API-02", "api-worker-1", "production", "singapore", "api", 4, 8, "dummy-gp-2x4", "", "", 2100000),
    ("SRV-API-03", "api-worker-2", "production", "singapore", "api", 4, 8, "dummy-gp-2x4", "", "", None),
    ("SRV-DB-01", "postgres-primary", "production", "jakarta", "db", 8, 32, "dummy-mem-4x16", "", "", 5200000),
    ("SRV-DB-02", "postgres-replica", "staging", "jakarta", "db", 4, 16, "dummy-mem-2x8", "", "", 2800000),
    ("SRV-BATCH-01", "nightly-batch", "staging", "jakarta", "batch", 4, 8, "dummy-gp-2x4", "", "", None),
    ("SRV-LEGACY-01", "legacy-erp", "staging", "jakarta", "erp", 2, 8, "dummy-old-1x4", "excluded",
     "Aplikasi legacy menunggu dekomisioning.", 1500000),
    ("SRV-DEV-01", "dev-sandbox", "dev", "jakarta", "web", 2, 4, "dummy-gp-1x2", "", "", None),
    ("SRV-DEV-02", "dev-integration", "dev", "jakarta", "api", 2, 4, "dummy-gp-1x2", "", "", None),
    ("SRV-DEV-03", "dev-batch", "dev", "jakarta", "batch", 2, 4, "dummy-gp-1x2", "", "", None),
]

BASE_LOAD = {"web": 32, "api": 46, "db": 62, "batch": 58, "erp": 18}
PHASE = {"web": 0.4, "api": 1.1, "db": 2.0, "batch": 2.8, "erp": 1.7}
START = datetime(2026, 1, 1, 0, 0, 0)
HOURS = 31 * 24


def _inventory_csv() -> str:
    header = (
        "ID server,Nama/alias,Environment,Region,Workload,vCPU,RAM GiB,Tipe instance,"
        "Status scope,Alasan pengecualian,Harga,Mata uang,Satuan harga,"
        "Label satuan lainnya,Tanggal sumber harga,Catatan"
    )
    lines = [header]
    for code, name, env, region, workload, vcpu, ram, instance, scope, reason, price in SERVERS:
        price_fields = (
            f"{price},IDR,per_month,,2025-12-15" if price is not None else ",,,,"
        )
        lines.append(
            f"{code},{name},{env},{region},{workload},{vcpu},{ram},{instance},"
            f"{scope},{reason},{price_fields},Data dummy"
        )
    return "\n".join(lines) + "\n"


def _value(server_index: int, code: str, workload: str, hour_index: int, memory: bool) -> float:
    rng = random.Random(f"{code}-{'mem' if memory else 'cpu'}-{hour_index}")
    base = BASE_LOAD[workload]
    day_hour = hour_index % 24
    daily = math.sin((day_hour - 6) / 24 * 2 * math.pi + PHASE[workload]) * 14
    trend = math.sin(hour_index / 24 / 31 * 2 * math.pi + server_index) * 4
    noise = rng.uniform(-4.5, 4.5)
    value = base + daily + trend + noise
    if server_index == 1:
        value -= 12
    if server_index == 4:
        value += 18
    if server_index == 7 and 8 <= day_hour <= 11:
        value += 22
    if memory:
        value = value * 1.1 + 5
    if server_index == 5:
        value = min(value, 72)
    return max(1.0, min(99.0, round(value, 2)))


def _timeseries_csv(memory: bool) -> str:
    lines = ["ID server,Timestamp,Nilai utilization (%)"]
    for index, (code, _name, _env, _region, workload, *_rest) in enumerate(SERVERS):
        for hour in range(HOURS):
            if code == "SRV-WEB-02" and hour % 31 in (5, 6):
                continue
            if code == "SRV-DB-01" and hour % 97 < 4:
                continue
            if memory and code == "SRV-API-03":
                continue
            if memory and code == "SRV-BATCH-01" and hour % 53 == 0:
                continue
            timestamp = (START + timedelta(hours=hour)).strftime("%Y-%m-%d %H:%M:%S")
            value = _value(index, code, workload, hour, memory)
            lines.append(f"{code},{timestamp},{value:.2f}")
    return "\n".join(lines) + "\n"


def generate(target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "inventaris_dummy.csv": _inventory_csv(),
        "cpu_dummy.csv": _timeseries_csv(memory=False),
        "memory_dummy.csv": _timeseries_csv(memory=True),
        "baca_saya.txt": (
            "Dataset dummy deterministik untuk Cloud Utilization & Rightsizing Simulator.\n"
            "Semua server, harga, dan nilai utilization bersifat fiktif.\n"
            "Timestamp memakai zona waktu Asia/Jakarta tanpa offset; metadata batch menyatakan Asia/Jakarta.\n"
            "Beberapa timestamp sengaja dihilangkan untuk menunjukkan gap/kelengkapan data.\n"
            "SRV-API-03 tidak memiliki data memory; SRV-LEGACY-01 dikecualikan manual; environment dev dikecualikan oleh aturan.\n"
        ),
    }
    paths = []
    for filename, content in files.items():
        path = target_dir / filename
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Buat dataset dummy deterministik.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    for path in generate(args.dir):
        print(path)


if __name__ == "__main__":
    main()
