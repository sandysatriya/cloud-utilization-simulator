import re

import pandas as pd
import streamlit as st

from cloudsim.io.readers import read_table
from cloudsim.services.import_common import issues_frame
from cloudsim.ui.format import local_time

NONE_OPTION = "(tidak dipetakan)"

ALIASES = {
    "server_code": ["id server", "server id", "server_code", "kode server", "hostname", "host", "vm"],
    "name": ["nama", "nama alias", "name", "alias"],
    "environment": ["environment", "env"],
    "region": ["region", "wilayah"],
    "workload": ["workload", "beban kerja"],
    "vcpu": ["vcpu", "v cpu", "cpu count", "jumlah vcpu", "cores"],
    "ram_gib": ["ram gib", "ram_gib", "ram", "memory gib", "memori gib"],
    "instance_type": ["tipe instance", "instance type", "instance_type"],
    "scope_status": ["status scope", "scope status", "scope", "in scope"],
    "exclusion_reason": ["alasan pengecualian", "exclusion reason", "alasan"],
    "price_amount": ["harga", "price", "price amount", "biaya"],
    "price_currency": ["mata uang", "currency", "price currency"],
    "price_unit": ["satuan harga", "price unit", "unit"],
    "price_unit_label": ["label satuan lainnya", "price unit label"],
    "price_source_date": ["tanggal sumber harga", "price source date", "tanggal harga"],
    "notes": ["catatan", "notes", "keterangan"],
    "timestamp": ["timestamp", "datetime", "date time", "waktu", "time"],
    "value": [
        "nilai utilization", "nilai utilization %", "nilai", "value", "utilization",
        "utilization %", "cpu utilization", "memory utilization", "pemakaian",
    ],
}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def auto_mapping(columns: list[str], fields: list[dict]) -> dict:
    result = {}
    normalized = {normalize(col): col for col in columns}
    for field in fields:
        key = field["key"]
        candidates = [field["label"], key, *ALIASES.get(key, [])]
        for candidate in candidates:
            found = normalized.get(normalize(candidate))
            if found:
                result[key] = found
                break
    return result


def mapping_widgets(columns: list[str], fields: list[dict], prefix: str,
                    defaults: dict | None = None) -> dict:
    defaults = defaults or auto_mapping(columns, fields)
    mapping = {}
    options = [NONE_OPTION, *columns]
    for field in fields:
        key = field["key"]
        current = defaults.get(key)
        index = options.index(current) if current in options else 0
        label = field["label"] + (" *" if field["required"] else "")
        mapping[key] = st.selectbox(
            label, options=options, index=index, key=f"{prefix}_{key}",
            help="Kolom sumber yang dipetakan ke field ini.",
        )
    return {key: value for key, value in mapping.items() if value != NONE_OPTION}


def file_reading_controls(data: bytes, filename: str, *, key_prefix: str) -> dict:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    options = {"sheet": None, "delimiter": ",", "header_row": 1}
    if suffix in {"xlsx", "xlsm"}:
        from cloudsim.io.readers import list_sheets
        sheets = list_sheets(data)
        options["sheet"] = st.selectbox("Sheet", sheets, key=f"{key_prefix}_sheet")
    elif suffix == "csv":
        from cloudsim.io.readers import CSV_DELIMITERS
        delimiter = st.selectbox(
            "Pemisah kolom", options=list(CSV_DELIMITERS),
            format_func=lambda value: CSV_DELIMITERS[value],
            key=f"{key_prefix}_delimiter",
        )
        options["delimiter"] = delimiter
    options["header_row"] = int(st.number_input(
        "Baris header", min_value=1, max_value=50, value=1, step=1,
        key=f"{key_prefix}_header",
    ))
    return options


def load_columns(data: bytes, filename: str, controls: dict) -> list[str] | None:
    try:
        df = read_table(
            data, filename,
            sheet=controls.get("sheet"),
            delimiter=controls.get("delimiter", ","),
            header_row=controls.get("header_row", 1),
        )
    except Exception as exc:
        st.error(str(exc))
        return None
    st.caption(f"{len(df)} baris terbaca. Pratinjau 5 baris pertama:")
    st.dataframe(df.head(5), width="stretch", hide_index=True)
    return [str(col) for col in df.columns]


def show_preview(preview, *, timezone_name: str | None = None) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total baris", preview.total_rows)
    col2.metric("Baris valid", preview.accepted_count)
    col3.metric("Error", len(preview.errors))
    col4.metric("Peringatan", len(preview.warnings))
    if preview.period_start_utc is not None and preview.period_end_utc is not None:
        tz = timezone_name or "UTC"
        st.caption(
            f"Rentang data: {local_time(preview.period_start_utc, tz)} s.d. "
            f"{local_time(preview.period_end_utc, tz)} ({tz})"
        )
    if preview.server_summary:
        frame = pd.DataFrame(preview.server_summary)
        for column in ("Rentang awal", "Rentang akhir"):
            if column in frame:
                frame[column] = frame[column].map(
                    lambda ts: local_time(ts, timezone_name or "UTC")
                )
        st.dataframe(frame, width="stretch", hide_index=True)
    elif preview.accepted_rows:
        rows = preview.accepted_rows
        if isinstance(rows[0], dict) and "_display" in rows[0]:
            rows = [row["_display"] for row in rows]
        try:
            st.dataframe(pd.DataFrame(rows).head(100), width="stretch", hide_index=True)
        except Exception:
            pass
    issues = preview.errors + preview.warnings
    if issues:
        st.dataframe(issues_frame(issues), width="stretch", hide_index=True)
    if preview.errors:
        st.error(
            "Ada baris bermasalah. Import diblokir kecuali Anda secara eksplisit "
            "memilih menyimpan hanya baris valid."
        )
    else:
        st.success("Tidak ada error pada pratinjau. Data belum disimpan.")
