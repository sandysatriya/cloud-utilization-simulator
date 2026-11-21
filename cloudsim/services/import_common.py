import hashlib
from dataclasses import dataclass, field


@dataclass
class ImportPreview:
    kind: str
    file_name: str
    file_sha256: str
    total_rows: int
    accepted_count: int
    accepted_rows: list[dict]
    errors: list[dict]
    warnings: list[dict]
    metadata: dict = field(default_factory=dict)
    server_summary: list[dict] = field(default_factory=list)
    period_start_utc: int | None = None
    period_end_utc: int | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def issue(severity: str, code: str, row_ref, detail: str) -> dict:
    return {
        "severity": severity,
        "code": code,
        "row_ref": str(row_ref) if row_ref is not None else "",
        "detail": detail,
    }


def issues_frame(issues: list[dict]):
    import pandas as pd
    rows = [
        {
            "Tingkat": "Error" if i["severity"] == "error" else "Peringatan",
            "Kode": i["code"],
            "Baris": i["row_ref"],
            "Detail": i["detail"],
        }
        for i in issues
    ]
    return pd.DataFrame(rows, columns=["Tingkat", "Kode", "Baris", "Detail"])
