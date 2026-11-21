from datetime import datetime

import streamlit as st

from cloudsim.errors import AppError
from cloudsim.services import (
    baseline_service,
    export_service,
    kpi_service,
    simulation_service,
)
from cloudsim.ui.context import build_analysis, normalize_selection


def _kpi_results(analysis) -> list[dict]:
    results = []
    for item in kpi_service.list_definitions():
        definition = kpi_service.get_definition(item["id"])
        evaluation = {"available": False, "reason": "KPI belum disetujui.",
                      "status": definition.get("status")}
        if definition.get("status") == "approved":
            baseline = None
            if definition.get("scope_mode") == "baseline_scope" and definition.get("baseline_id"):
                try:
                    baseline = baseline_service.get_baseline(definition["baseline_id"])
                except AppError:
                    baseline = None
            evaluation = kpi_service.evaluate_definition(definition, analysis, baseline)
        results.append({"definition": definition, "evaluation": evaluation})
    return results


def render(filters: dict | None) -> None:
    st.title("Export Excel")
    st.caption(
        "Export berisi ringkasan, statistik, pengecualian, sumber data, baseline, simulasi, "
        "KPI, asumsi, dan peringatan. Data sampel mentah tidak diekspor."
    )
    analysis = build_analysis(filters)
    if analysis is None:
        return

    baselines = baseline_service.list_baselines()
    comparison = None
    baseline_options = ["none", *[item["id"] for item in baselines]]
    if baselines:
        normalize_selection("export_baseline", baseline_options, "none")
        selected_baseline = st.selectbox(
            "Sertakan perbandingan baseline",
            options=baseline_options,
            format_func=lambda value: "Tidak disertakan" if value == "none" else next(
                f"#{item['id']} {item['name']}" for item in baselines if item["id"] == value
            ),
            key="export_baseline",
        )
        if selected_baseline != "none":
            try:
                comparison = baseline_service.compare(selected_baseline, analysis)
            except AppError as exc:
                st.error(str(exc))
    else:
        st.caption("Belum ada baseline.")

    simulations = simulation_service.list_simulations()
    simulation = None
    if simulations:
        sim_options = ["none", *[item["id"] for item in simulations]]
        normalize_selection("export_simulation", sim_options, "none")
        selected_simulation = st.selectbox(
            "Sertakan simulasi tersimpan",
            options=sim_options,
            format_func=lambda value: "Tidak disertakan" if value == "none" else next(
                f"#{item['id']} {item['name']} ({item['server_code']})"
                for item in simulations if item["id"] == value
            ),
            key="export_simulation",
        )
        if selected_simulation != "none":
            try:
                simulation = simulation_service.get_simulation(selected_simulation)
            except AppError as exc:
                st.error(str(exc))
    else:
        st.caption("Belum ada simulasi tersimpan.")

    kpi_results = _kpi_results(analysis)
    if not any(entry["definition"].get("status") == "approved" for entry in kpi_results):
        st.info("KPI belum dikonfigurasi/disetujui; sheet KPI akan menyatakan Belum Dikonfigurasi.")

    st.markdown("**Isi export**")
    st.write(
        "- Ringkasan periode, sumber, formula, dan ambang\n"
        "- Statistik per server dan kualitas data\n"
        "- Daftar server dikecualikan beserta alasan\n"
        "- Metadata batch sumber\n"
        "- Delta baseline (jika dipilih), dengan pemisahan pp dan persen relatif\n"
        "- Hasil simulasi (jika dipilih) dan asumsi\n"
        "- KPI yang disetujui dan hasil evaluasinya\n"
        "- Asumsi, batasan, dan peringatan"
    )
    if st.button("Buat file Excel", type="primary"):
        try:
            data = export_service.build_export(
                analysis,
                simulation=simulation,
                comparison=comparison,
                kpi_results=kpi_results,
            )
        except Exception as exc:
            st.error(f"Export gagal: {exc}")
        else:
            st.session_state["export_bytes"] = data
            st.session_state["export_name"] = (
                "cloudsim_export_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
            )
    data = st.session_state.get("export_bytes")
    if data:
        st.download_button(
            "Unduh file Excel",
            data=data,
            file_name=st.session_state.get("export_name", "cloudsim_export.xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.caption(
            "Nilai teks diamankan dari formula injection. File tidak berisi makro atau tautan eksternal."
        )
