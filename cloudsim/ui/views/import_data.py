import pandas as pd
import streamlit as st
from cloudsim.enums import STATISTIC_TYPES
from cloudsim.errors import AppError
from cloudsim.io.column_mapping import INVENTORY_FIELDS, TIMESERIES_FIELDS
from cloudsim.io.template_builder import (
    inventory_template_bytes,
    timeseries_template_csv_bytes,
)
from cloudsim.services import (
    batch_service,
    inventory_import_service,
    settings_service,
    timeseries_import_service,
)
from cloudsim.services.import_common import issues_frame, sha256_bytes
from cloudsim.ui.context import normalize_selection
from cloudsim.ui.format import local_time
from cloudsim.ui.import_helpers import (
    file_reading_controls,
    load_columns,
    mapping_widgets,
    show_preview,
)


def _template_downloads() -> None:
    col1, col2 = st.columns(2)
    col1.download_button(
        "Unduh template inventaris (XLSX)",
        data=inventory_template_bytes(),
        file_name="inventaris_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    col2.download_button(
        "Unduh template time series (CSV)",
        data=timeseries_template_csv_bytes(),
        file_name="time_series_template.csv",
        mime="text/csv",
        width="stretch",
    )


def _inventory_tab() -> None:
    st.subheader("Import inventaris server")
    st.write(
        "Format bebas selama kolom dapat dipetakan. Pratinjau dan validasi dilakukan "
        "sebelum data disimpan. Server dengan kode yang sudah ada tidak ditimpa."
    )
    _template_downloads()
    uploaded = st.file_uploader("File inventaris (CSV/XLSX)", type=["csv", "xlsx", "xlsm"],
                                key="inv_upload")
    if not uploaded:
        return
    data = uploaded.getvalue()
    prefix = f"inv_{sha256_bytes(data)[:10]}"
    controls = file_reading_controls(data, uploaded.name, key_prefix=prefix)
    columns = load_columns(data, uploaded.name, controls)
    if not columns:
        return
    st.markdown("**Pemetaan kolom**")
    mapping = mapping_widgets(columns, INVENTORY_FIELDS, prefix)
    if st.button("Pratinjau & validasi inventaris", type="primary"):
        try:
            preview = inventory_import_service.preview_inventory(
                data, uploaded.name, mapping,
                sheet=controls.get("sheet"),
                delimiter=controls.get("delimiter", ","),
                header_row=controls.get("header_row", 1),
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.session_state["inv_preview"] = preview
            st.session_state["inv_preview_key"] = prefix

    preview = st.session_state.get("inv_preview")
    if not preview or st.session_state.get("inv_preview_key") != prefix:
        return
    st.divider()
    st.markdown("**Pratinjau sebelum import**")
    show_preview(preview)
    allow_partial = st.checkbox(
        "Simpan hanya baris valid (baris error dilewati secara eksplisit)",
        disabled=not preview.errors, key=f"{prefix}_partial",
    )
    if st.button("Simpan inventaris", key=f"{prefix}_save", type="primary"):
        try:
            result = inventory_import_service.save_inventory_import(
                preview, allow_partial=allow_partial and bool(preview.errors)
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"Batch #{result['batch_id']} disimpan: {result['created']} server dibuat, "
                f"{result['skipped']} baris dilewati."
            )
            st.session_state.pop("inv_preview", None)
            st.rerun()


def _timeseries_tab() -> None:
    st.subheader("Import time series utilization")
    st.write(
        "Satu file berisi satu metrik (CPU atau memory). Data CPU dan memory boleh berasal "
        "dari file terpisah. Nilai kosong tidak dianggap nol dan tidak diisi otomatis."
    )
    settings = settings_service.get_settings()
    metric = st.selectbox(
        "Metrik file ini", options=["cpu", "memory"],
        format_func=lambda value: "CPU" if value == "cpu" else "Memory",
        key="ts_metric",
    )
    uploaded = st.file_uploader(
        "File time series (CSV/XLSX)", type=["csv", "xlsx", "xlsm"], key=f"ts_upload_{metric}"
    )
    if not uploaded:
        return
    data = uploaded.getvalue()
    prefix = f"ts_{metric}_{sha256_bytes(data)[:10]}"
    controls = file_reading_controls(data, uploaded.name, key_prefix=prefix)
    columns = load_columns(data, uploaded.name, controls)
    if not columns:
        return

    st.markdown("**Metadata sumber**")
    col1, col2 = st.columns(2)
    timezone_name = col1.text_input(
        "Zona waktu timestamp", value=settings["display_timezone"], key=f"{prefix}_tz",
        help="Contoh Asia/Jakarta, UTC, Asia/Singapore. Timestamp ber-offset tetap dihormati.",
    )
    interval_known = col1.checkbox(
        "Interval pengamatan diketahui", value=True, key=f"{prefix}_interval_known"
    )
    interval_minutes = None
    if interval_known:
        interval_minutes = col1.number_input(
            "Interval (menit)", min_value=1.0, max_value=1440.0, value=60.0, step=1.0,
            key=f"{prefix}_interval",
        )
    statistic_type = col2.selectbox(
        "Jenis statistik sumber", options=list(STATISTIC_TYPES),
        format_func=lambda value: STATISTIC_TYPES[value], key=f"{prefix}_stat",
    )
    statistic_label = None
    if statistic_type == "other":
        statistic_label = col2.text_input(
            "Label jenis statistik", key=f"{prefix}_stat_label",
            help="Wajib untuk jenis Lainnya, misalnya rata-rata 5 menit.",
        )
    date_format = col2.selectbox(
        "Format timestamp", options=["iso", "dmy_slash", "mdy_slash", "dmy_dash"],
        format_func=lambda value: {
            "iso": "ISO 8601 (2026-01-31 23:00:00)",
            "dmy_slash": "DD/MM/YYYY HH:MM",
            "mdy_slash": "MM/DD/YYYY HH:MM",
            "dmy_dash": "DD-MM-YYYY HH:MM",
        }[value],
        key=f"{prefix}_datefmt",
    )
    decimal_format = col2.selectbox(
        "Format desimal", options=["dot", "comma"],
        format_func=lambda value: "Titik (12.5)" if value == "dot" else "Koma (12,5)",
        key=f"{prefix}_decimal",
    )

    st.markdown("**Pemetaan kolom**")
    mapping = mapping_widgets(columns, TIMESERIES_FIELDS, prefix)
    if st.button("Pratinjau & validasi time series", type="primary", key=f"{prefix}_preview"):
        try:
            preview = timeseries_import_service.preview_timeseries(
                data, uploaded.name, mapping,
                metric=metric,
                timezone_name=timezone_name,
                interval_minutes=float(interval_minutes) if interval_minutes else None,
                statistic_type=statistic_type,
                statistic_label=statistic_label,
                date_format=date_format,
                decimal_format=decimal_format,
                sheet=controls.get("sheet"),
                delimiter=controls.get("delimiter", ","),
                header_row=controls.get("header_row", 1),
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.session_state["ts_preview"] = preview
            st.session_state["ts_preview_key"] = prefix

    preview = st.session_state.get("ts_preview")
    if not preview or st.session_state.get("ts_preview_key") != prefix:
        return
    st.divider()
    st.markdown("**Pratinjau sebelum import**")
    show_preview(preview, timezone_name=timezone_name)
    st.caption(
        "Kelengkapan di pratinjau dihitung dari rentang data yang diamati, bukan periode penuh. "
        "Kelengkapan periode analisis dihitung hanya bila interval diketahui."
    )
    allow_partial = st.checkbox(
        "Simpan hanya baris valid (baris error/konflik dilewati secara eksplisit)",
        disabled=not preview.errors, key=f"{prefix}_partial",
    )
    if st.button("Simpan time series", key=f"{prefix}_save", type="primary"):
        try:
            result = timeseries_import_service.save_timeseries_import(
                preview, allow_partial=allow_partial and bool(preview.errors)
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"Batch #{result['batch_id']} disimpan: {result['created']} sampel, "
                f"{result['skipped']} baris dilewati."
            )
            st.session_state.pop("ts_preview", None)
            st.rerun()


def _batch_tab() -> None:
    st.subheader("Batch data tersimpan")
    batches = batch_service.list_batches()
    if not batches:
        st.info("Belum ada batch.")
        return
    rows = []
    for batch in batches:
        rows.append({
            "ID": batch.id,
            "Jenis": batch.data_type,
            "File": batch.file_name,
            "Jenis statistik": batch.statistic_type or "-",
            "Interval (dtk)": batch.interval_seconds,
            "Zona waktu": batch.timezone or "-",
            "Rentang awal": local_time(batch.period_start_utc, batch.timezone or "UTC")
            if batch.period_start_utc else None,
            "Rentang akhir": local_time(batch.period_end_utc, batch.timezone or "UTC")
            if batch.period_end_utc else None,
            "Diterima": batch.accepted_rows,
            "Ditolak": batch.rejected_rows,
            "Diimpor": batch.imported_at,
            "SHA-256": batch.file_sha256[:16] + "…",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    normalize_selection("batch_detail", [batch.id for batch in batches])
    selected = st.selectbox(
        "Lihat detail batch", options=[batch.id for batch in batches],
        format_func=lambda batch_id: f"#{batch_id}",
        key="batch_detail",
    )
    issues = batch_service.list_issues(selected)
    if issues:
        st.markdown("**Catatan import**")
        st.dataframe(issues_frame(issues), width="stretch", hide_index=True)
    else:
        st.caption("Tidak ada catatan import untuk batch ini.")
    st.divider()
    st.markdown("**Hapus batch**")
    st.caption(
        "Menghapus batch menghapus sampel time series terkait. Snapshot baseline dan simulasi "
        "tetap menyimpan angka historis. Tindakan ini tidak dapat dibatalkan."
    )
    confirm = st.checkbox(f"Saya yakin menghapus batch #{selected}", key="batch_delete_confirm")
    if st.button("Hapus batch", disabled=not confirm, type="secondary"):
        batch_service.delete_batch(selected)
        st.success(f"Batch #{selected} dihapus.")
        st.rerun()


def render(_filters: dict | None = None) -> None:
    st.title("Import & Validasi Data")
    st.caption(
        "Data dummy digunakan selama pengembangan. Aplikasi tidak meminta kredensial cloud, "
        "tidak terhubung ke akun produksi, dan tidak menjalankan perintah cloud."
    )
    st.info(
        "Alur: unggah file → petakan kolom → pratinjau validasi → simpan. "
        "Duplikat konflik ditandai dan tidak dipilih diam-diam."
    )
    tab_inv, tab_ts, tab_batch = st.tabs(["Inventaris", "Time Series", "Batch Tersimpan"])
    with tab_inv:
        _inventory_tab()
    with tab_ts:
        _timeseries_tab()
    with tab_batch:
        _batch_tab()
