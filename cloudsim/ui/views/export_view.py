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


def render(filters: dict | None) -> None:
    st.title("Export Excel")
    st.caption(
        "Export berisi ringkasan, statistik, pengecualian, sumber data, baseline, simulasi, "
        "konfigurasi KPI, asumsi, dan peringatan. Data sampel mentah dapat disertakan opsional."
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

    kpi_definitions = [
        kpi_service.get_definition(item["id"]) for item in kpi_service.list_definitions()
    ]
    if not kpi_definitions:
        st.info("KPI belum dikonfigurasi; sheet KPI akan menyatakan Belum Dikonfigurasi.")

    cpu_rows = export_service.raw_sample_count(analysis, "cpu")
    memory_rows = export_service.raw_sample_count(analysis, "memory")
    include_raw = st.checkbox(
        f"Sertakan data sampel mentah ({cpu_rows:,} baris CPU, {memory_rows:,} baris memory)",
        key="export_include_raw",
    )
    if include_raw:
        st.caption(
            "Hanya server dalam scope dan periode yang dipilih. Nilai apa adanya; gap tidak diisi. "
            "Data besar membuat file dan proses export lebih lambat."
        )

    st.markdown("**Isi export**")
    st.write(
        "- Ringkasan periode, sumber, formula, dan ambang\n"
        "- Statistik per server dan kualitas data\n"
        "- Daftar server dikecualikan beserta alasan\n"
        "- Metadata batch sumber\n"
        "- Delta baseline (jika dipilih), dengan pemisahan pp dan persen relatif\n"
        "- Hasil simulasi (jika dipilih) dan asumsi\n"
        "- Konfigurasi KPI (tanpa perhitungan nilai)\n"
        "- Asumsi, batasan, dan peringatan\n"
        "- Data sampel mentah per metrik (jika dicentang)"
    )
    if st.button("Buat file Excel", type="primary"):
        try:
            data = export_service.build_export(
                analysis,
                simulation=simulation,
                comparison=comparison,
                kpi_definitions=kpi_definitions,
                include_raw_samples=include_raw,
            )
        except AppError as exc:
            st.session_state.pop("export_bytes", None)
            st.error(str(exc))
        except Exception as exc:
            st.session_state.pop("export_bytes", None)
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
