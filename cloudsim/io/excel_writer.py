import math
from datetime import date, datetime
from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from cloudsim.io.sanitize import sanitize_text

INVALID_SHEET_CHARS = set('[]:*?/\\')


def safe_sheet_name(name: str, used: set[str] | None = None) -> str:
    cleaned = "".join(ch for ch in str(name) if ch not in INVALID_SHEET_CHARS)[:31] or "Sheet"
    if used is None:
        used = set()
    candidate = cleaned
    index = 2
    while candidate in used:
        suffix = f"_{index}"
        candidate = cleaned[:31 - len(suffix)] + suffix
        index += 1
    used.add(candidate)
    return candidate


def _cell_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return sanitize_text(value)
    if hasattr(value, "item") and not isinstance(value, (bytes, bytearray)):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def workbook_bytes(sheets: list[tuple[str, pd.DataFrame]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    for name, df in sheets:
        ws = wb.create_sheet(safe_sheet_name(name, used))
        headers = [str(c) for c in df.columns]
        ws.append([sanitize_text(h) for h in headers])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in df.itertuples(index=False, name=None):
            ws.append([_cell_value(v) for v in row])
        ws.freeze_panes = "A2"
        for idx, header in enumerate(headers, start=1):
            width = min(max(len(header) + 2, 12), 45)
            ws.column_dimensions[get_column_letter(idx)].width = width
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
