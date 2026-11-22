import pandas as pd
import streamlit as st

from cloudsim.analysis.kpi import ALLOWED_AGGREGATES, ALLOWED_MEASURES, ALLOWED_METRICS, ALLOWED_OPERATORS
from cloudsim.enums import AGGREGATE_METHODS, KPI_MEASURES, KPI_OPERATORS, KPI_STATUS
from cloudsim.errors import AppError
from cloudsim.services import baseline_service, kpi_service
from cloudsim.ui.context import normalize_selection


METRIC_LABELS = {"cpu": "CPU", "memory": "Memory"}
SCOPE_MODES = {"current_scope": "Scope saat ini", "baseline_scope": "Scope baseline"}


def _optional_float(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


def _threshold_frame(definition: dict | None) -> pd.DataFrame:
    rows = (definition or {}).get("thresholds") or []
    return pd.DataFrame([
        {
            "label": row.get("label"),
            "min_value": row.get("min_value"),
            "max_value": row.get("max_value"),
            "meaning": row.get("meaning"),
        }
        for row in rows
    ], columns=["label", "min_value", "max_value", "meaning"])


def _definition_form(definition: dict | None, baselines: list[dict]) -> None:
    kpi_id = definition.get("id") if definition else None
    prefix = f"kpi_{kpi_id or 'new'}"
    if definition and definition.get("status") == "approved":
        st.warning(
            "Definisi ini sedang disetujui. Menyimpan sebagai draf akan mencabut status "
            "disetujui sampai Anda menyetujui ulang."
        )
    baseline_by_id = {item["id"]: item for item in baselines}
    with st.form(f"kpi_form_{kpi_id or 'new'}"):
        name = st.text_input("Nama KPI *", value=(definition or {}).get("name") or "",
                             key=f"{prefix}_name")
        description = st.text_area(
            "Deskripsi", value=(definition or {}).get("description") or "",
            key=f"{prefix}_description",
        )
        col1, col2 = st.columns(2)
        metric = col1.selectbox(
            "Metrik *", options=list(ALLOWED_METRICS),
            format_func=lambda value: METRIC_LABELS[value],
            index=list(ALLOWED_METRICS).index((definition or {}).get("metric"))
            if (definition or {}).get("metric") in ALLOWED_METRICS else 0,
            key=f"{prefix}_metric",
        )
        measure = col2.selectbox(
            "Measure *", options=list(ALLOWED_MEASURES),
            format_func=lambda value: KPI_MEASURES[value],
            index=list(ALLOWED_MEASURES).index((definition or {}).get("measure"))
            if (definition or {}).get("measure") in ALLOWED_MEASURES else 0,
            key=f"{prefix}_measure",
        )
        aggregate = col1.selectbox(
            "Agregasi antarserver *", options=list(ALLOWED_AGGREGATES),
            format_func=lambda value: AGGREGATE_METHODS[value],
            index=list(ALLOWED_AGGREGATES).index((definition or {}).get("aggregate_method"))
            if (definition or {}).get("aggregate_method") in ALLOWED_AGGREGATES else 0,
            key=f"{prefix}_aggregate",
        )
        operator = col2.selectbox(
            "Operator *", options=list(ALLOWED_OPERATORS),
            format_func=lambda value: KPI_OPERATORS[value],
            index=list(ALLOWED_OPERATORS).index((definition or {}).get("operator"))
            if (definition or {}).get("operator") in ALLOWED_OPERATORS else 0,
            key=f"{prefix}_operator",
        )
        target = col1.number_input(
            "Target (%) *", min_value=0.0, max_value=100.0,
            value=float((definition or {}).get("target_value") or 0.0), step=0.1,
            key=f"{prefix}_target",
        )
        upper = col2.number_input(
            "Batas atas (%) untuk operator between", min_value=0.0, max_value=100.0,
            value=float((definition or {}).get("target_value_upper") or 0.0), step=0.1,
            key=f"{prefix}_upper",
        )
        scope_mode = col1.selectbox(
            "Scope KPI", options=list(SCOPE_MODES),
            format_func=lambda value: SCOPE_MODES[value],
            index=list(SCOPE_MODES).index((definition or {}).get("scope_mode"))
            if (definition or {}).get("scope_mode") in SCOPE_MODES else 0,
            key=f"{prefix}_scope_mode",
        )
        baseline_options = [item["id"] for item in baselines]
        current_baseline = (definition or {}).get("baseline_id")
        baseline_index = (
            baseline_options.index(current_baseline) if current_baseline in baseline_options else 0
        )
        baseline_id = None
        if baseline_options:
            baseline_id = col2.selectbox(
                "Baseline untuk scope", options=baseline_options,
                format_func=lambda value: f"#{value} {baseline_by_id[value]['name']}",
                index=baseline_index, key=f"{prefix}_baseline",
            )
        else:
            col2.caption("Belum ada baseline.")
        st.markdown("**Batas capaian (dokumentasi, tidak dipakai untuk menghitung otomatis)**")
        thresholds = st.data_editor(
            _threshold_frame(definition),
            num_rows="dynamic", width="stretch",
            key=f"{prefix}_thresholds",
            column_config={
                "label": st.column_config.TextColumn("Label"),
                "min_value": st.column_config.NumberColumn("Batas bawah (%)", min_value=0, max_value=100),
                "max_value": st.column_config.NumberColumn("Batas atas (%)", min_value=0, max_value=100),
                "meaning": st.column_config.TextColumn("Makna"),
            },
        )
        save_draft = st.form_submit_button("Simpan draf", type="primary")
        approve = st.form_submit_button("Setujui definisi")
    if not (save_draft or approve):
        return
    threshold_rows = []
    for _, row in thresholds.iterrows():
        threshold_rows.append({
            "label": row.get("label") or "Batas",
            "min_value": _optional_float(row.get("min_value")),
            "max_value": _optional_float(row.get("max_value")),
            "meaning": row.get("meaning"),
        })
    if operator == "between" and upper < target:
        st.error("Batas atas tidak boleh lebih kecil dari target.")
        return
    payload = {
        "name": name,
        "description": description,
        "metric": metric,
        "measure": measure,
        "aggregate_method": aggregate,
        "operator": operator,
        "target_value": target,
        "target_value_upper": upper if operator == "between" else None,
        "scope_mode": scope_mode,
        "baseline_id": baseline_id if scope_mode == "baseline_scope" else None,
        "status": "draft",
    }
    try:
        saved_id = kpi_service.save_definition(
            payload, threshold_rows, kpi_id, approve=approve
        )
    except AppError as exc:
        st.error(str(exc))
    else:
        st.success(
            f"Definisi KPI #{saved_id} {'disetujui' if approve else 'disimpan sebagai draf'}."
        )
        st.session_state["kpi_pending_id"] = saved_id
        st.rerun()


def _definitions_tab(baselines: list[dict]) -> None:
    definitions = kpi_service.list_definitions()
    approved = [item for item in definitions if item["status"] == "approved"]
    if approved:
        st.success(
            f"{len(approved)} definisi KPI disetujui. Perhitungan KPI belum tersedia; "
            "definisi hanya disimpan sebagai konfigurasi."
        )
    else:
        st.info("Modul KPI: Belum Dikonfigurasi. Formula KPI tidak dibuat otomatis oleh aplikasi.")
    if definitions:
        st.dataframe(pd.DataFrame([{
            "ID": item["id"],
            "Nama": item["name"],
            "Status": KPI_STATUS.get(item["status"], item["status"]),
            "Metrik": METRIC_LABELS.get(item["metric"], item["metric"]),
            "Measure": KPI_MEASURES.get(item["measure"], item["measure"]),
            "Agregasi": AGGREGATE_METHODS.get(item["aggregate_method"], item["aggregate_method"]),
            "Operator": KPI_OPERATORS.get(item["operator"], item["operator"]),
            "Target": item["target_value"],
            "Disetujui": item["approved_at"],
            "Versi formula": item["formula_version"],
        } for item in definitions]), width="stretch", hide_index=True)

    options = ["new", *[item["id"] for item in definitions]]
    pending = st.session_state.pop("kpi_pending_id", None)
    if pending is not None:
        st.session_state["kpi_edit_select"] = pending
    normalize_selection("kpi_edit_select", options, "new")
    selected = st.selectbox(
        "Pilih definisi", options=options,
        format_func=lambda value: "Definisi baru" if value == "new" else next(
            f"#{item['id']} {item['name']}" for item in definitions if item["id"] == value
        ),
        key="kpi_edit_select",
    )
    definition = None if selected == "new" else kpi_service.get_definition(selected)
    st.subheader("Editor definisi")
    _definition_form(definition, baselines)

    if definition:
        st.divider()
        st.subheader("Status dan penghapusan")
        if definition["status"] == "approved":
            confirm = st.checkbox(
                f"Saya yakin mencabut persetujuan KPI #{definition['id']}",
                key="kpi_revoke_confirm",
            )
            if st.button("Cabut persetujuan", disabled=not confirm):
                kpi_service.revoke_definition(definition["id"])
                st.success("Persetujuan dicabut; KPI kembali menjadi draf.")
                st.rerun()
        confirm_delete = st.checkbox(
            f"Saya yakin menghapus definisi KPI #{definition['id']}", key="kpi_delete_confirm"
        )
        if st.button("Hapus definisi KPI", disabled=not confirm_delete):
            kpi_service.delete_definition(definition["id"])
            st.session_state["kpi_pending_id"] = "new"
            st.success("Definisi KPI dihapus.")
            st.rerun()


def render(filters: dict | None) -> None:
    st.title("Konfigurasi KPI")
    st.caption(
        "Formula KPI tidak dibuat oleh aplikasi. Modul ini hanya menyimpan konfigurasi KPI; "
        "nilai KPI belum dihitung pada versi ini."
    )
    _definitions_tab(baseline_service.list_baselines())
