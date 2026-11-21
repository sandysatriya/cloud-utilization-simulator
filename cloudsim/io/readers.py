import io
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from cloudsim.errors import ValidationError

CSV_DELIMITERS = {",": "Koma (,)", ";": "Titik koma (;)", "\t": "Tab"}


def list_sheets(data: bytes) -> list[str]:
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True)
    except Exception:
        raise ValidationError("File Excel tidak dapat dibaca.")
    return list(wb.sheetnames)


def read_table(
    data: bytes,
    filename: str,
    *,
    sheet: str | None = None,
    delimiter: str = ",",
    header_row: int = 1,
) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if header_row < 1:
        raise ValidationError("Baris header harus minimal 1.")
    try:
        if suffix == ".csv":
            df = pd.read_csv(
                io.BytesIO(data), sep=delimiter, header=header_row - 1,
                dtype=str, keep_default_na=False, encoding="utf-8-sig",
            )
        elif suffix in {".xlsx", ".xlsm"}:
            df = pd.read_excel(
                io.BytesIO(data), sheet_name=sheet or 0, header=header_row - 1,
                engine="openpyxl", dtype=object,
            )
        else:
            raise ValidationError("Format file harus CSV atau XLSX.")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"File tidak dapat dibaca: {exc}")

    columns = [str(c).strip() for c in df.columns]
    if any((not col) or col.lower().startswith("unnamed:") for col in columns):
        raise ValidationError("Header kolom tidak boleh kosong. Periksa baris header.")
    if len(set(c.lower() for c in columns)) != len(columns):
        raise ValidationError("Header kolom duplikat; gunakan nama kolom yang unik.")
    df.columns = columns
    return df


def preview_rows(df: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    return df.head(limit).copy()
