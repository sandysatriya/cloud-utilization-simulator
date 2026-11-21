import pandas as pd
import streamlit as st

from cloudsim.analysis.kpi import ALLOWED_AGGREGATES, ALLOWED_MEASURES, ALLOWED_METRICS, ALLOWED_OPERATORS
from cloudsim.enums import AGGREGATE_METHODS, KPI_MEASURES, KPI_OPERATORS, KPI_STATUS
from cloudsim.errors import AppError
from cloudsim.services import baseline_service, kpi_service
from cloudsim.ui.context import build_analysis, normalize_selection
from cloudsim.ui.format import number, pct


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
            "Scope evaluasi", options=list(SCOPE_MODES),
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
        approve = st.form_submit_button("Setujui & aktifkan")
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
        st.success(f"{len(approved)} KPI disetujui dan siap dievaluasi.")
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


def _evaluation_tab(analysis) -> None:
    definitions = kpi_service.list_definitions()
    if not definitions:
        st.info("Belum Dikonfigurasi. Buat dan setujui definisi KPI terlebih dahulu.")
        return
    normalize_selection("kpi_eval_select", [item["id"] for item in definitions])
    selected_id = st.selectbox(
        "Pilih KPI", options=[item["id"] for item in definitions],
        format_func=lambda value: next(
            f"#{item['id']} {item['name']} ({KPI_STATUS.get(item['status'], item['status'])})"
            for item in definitions if item["id"] == value
        ),
        key="kpi_eval_select",
    )
    definition = kpi_service.get_definition(selected_id)
    st.markdown(
        f"**Status:** {KPI_STATUS.get(definition['status'], definition['status'])} | "
        f"**Metrik:** {METRIC_LABELS.get(definition['metric'], '-')} | "
        f"**Measure:** {KPI_MEASURES.get(definition['measure'], '-')} | "
        f"**Agregasi:** {AGGREGATE_METHODS.get(definition['aggregate_method'], '-')}"
    )
    if definition["status"] != "approved":
        st.info(
            "KPI belum disetujui sehingga tidak dihitung. Modul ini tidak mengarang formula "
            "dan tidak memakai eval/kode bebas."
        )
        return
    baseline = None
    if definition["scope_mode"] == "baseline_scope" and definition.get("baseline_id"):
        try:
            baseline = baseline_service.get_baseline(definition["baseline_id"])
        except AppError as exc:
            st.error(str(exc))
            return
        st.caption(
            f"Scope baseline: #{baseline['id']} {baseline['name']} "
            f"(formula {baseline['formula_version']})."
        )
    result = kpi_service.evaluate_definition(definition, analysis, baseline)
    if not result.get("available"):
        st.warning(result.get("reason") or "KPI tidak dapat dievaluasi.")
        return
    if result.get("aggregate_method") == "none":
        st.metric("Jumlah server lulus", f"{result['passed_count']} / {result['total_count']}")
        st.dataframe(pd.DataFrame([{
            "Kode server": item["server_code"],
            "Nilai (%)": number(item["value"]),
            "Lulus": "Ya" if item["passed"] else "Tidak",
        } for item in result["per_server"]]), width="stretch", hide_index=True)
    else:
        col1, col2 = st.columns(2)
        col1.metric("Nilai agregat", pct(result["aggregate_value"]))
        col2.metric(
            "Evaluasi target",
            "Lulus" if result["evaluated"] else "Tidak lulus"
            if result["evaluated"] is not None else "Tidak tersedia",
        )
        st.caption(
            f"Target: {KPI_OPERATORS.get(definition['operator'])} "
            f"{definition['target_value']}"
            + (f" s.d. {definition['target_value_upper']}"
               if definition.get("target_value_upper") is not None else "")
        )
        if result.get("aggregate_disclaimer"):
            st.info(result["aggregate_disclaimer"])
        st.caption(
            "Nilai agregat memakai metode yang dipilih pengguna. Rata-rata sederhana "
            "antarserver bukan utilization seluruh kapasitas."
        )
    st.caption(
        f"Versi formula KPI: {result.get('formula_version') or '-'}. "
        "Batas capaian hanya dokumentasi; evaluasi memakai target/operator di atas."
    )


def render(filters: dict | None) -> None:
    st.title("Konfigurasi KPI")
    st.caption(
        "Formula KPI tidak dibuat oleh aplikasi. Modul tetap Belum Dikonfigurasi sampai "
        "definisi disetujui pengguna."
    )
    analysis = build_analysis(filters)
    if analysis is None:
        return
    baselines = baseline_service.list_baselines()
    tab_def, tab_eval = st.tabs(["Definisi & Approval", "Evaluasi"])
    with tab_def:
        _definitions_tab(baselines)
    with tab_eval:
        _evaluation_tab(analysis)
