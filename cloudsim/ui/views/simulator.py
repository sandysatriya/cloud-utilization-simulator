from datetime import date

import pandas as pd
import streamlit as st

from cloudsim.config import PRICE_UNITS
from cloudsim.enums import ESTIMATE_FLAGS
from cloudsim.errors import AppError
from cloudsim.services import simulation_service, settings_service
from cloudsim.ui.context import build_analysis, normalize_selection
from cloudsim.ui.format import flag_labels, number, pct


METRIC_LABELS = {"cpu": "CPU", "memory": "Memory"}
MEASURE_LABELS = {"avg": "Rata-rata", "p95": "P95", "max": "Maksimum"}
REASON_LABELS = {
    "no_samples": "Tidak ada sampel",
    "low_samples": "Jumlah sampel di bawah ambang",
    "completeness_unavailable": "Kelengkapan tidak dapat dihitung",
    "low_completeness": "Kelengkapan di bawah ambang",
    "not_analyzed": "Metrik tidak dianalisis",
}


def _source_panel(analysis, server_code: str) -> None:
    rows = []
    for metric in ("cpu", "memory"):
        item = analysis.stats_for(server_code, metric)
        if item is None:
            continue
        rows.append({
            "Metrik": METRIC_LABELS[metric],
            "Sampel": item.sample_count,
            "Kelengkapan": pct(item.completeness_pct),
            "Rata-rata": number(item.avg),
            "P95": number(item.p95),
            "Maksimum": number(item.max),
            "Flag": flag_labels(item.flags),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _result_frame(result: dict) -> pd.DataFrame:
    rows = []
    for item in result["results"]:
        rows.append({
            "Metrik": METRIC_LABELS[item["metric"]],
            "Statistik": MEASURE_LABELS[item["stat_name"]],
            "Sebelum (%)": number(item["before"]),
            "Sesudah estimasi (%)": number(item["after"]),
            "Status": ESTIMATE_FLAGS.get(item["flag"], item["flag"]),
        })
    return pd.DataFrame(rows)


def _show_result(result: dict) -> None:
    st.subheader("Hasil estimasi")
    st.markdown(
        f"**{result['server_code']}:** {result['server'].vcpu} vCPU / "
        f"{number(result['server'].ram_gib, 1)} GiB → "
        f"{result['target_vcpu']} vCPU / {number(result['target_ram_gib'], 1)} GiB"
    )
    if result["target_instance_type"]:
        st.warning(
            f"Tipe instance target '{result['target_instance_type']}' belum tervalidasi. "
            "Aplikasi tidak memeriksa ketersediaan atau kecocokan tipe instance."
        )
    if not result["data_sufficient"]:
        details = []
        for metric, item in result["metric_sufficiency"].items():
            if not item["sufficient"]:
                reasons = ", ".join(REASON_LABELS.get(r, r) for r in item["reasons"])
                details.append(f"{METRIC_LABELS[metric]}: {reasons}")
        st.warning(
            "Data belum cukup untuk estimasi yang kuat. " + "; ".join(details)
            + ". Hasil tetap ditampilkan dengan status Data belum cukup."
        )

    frame = _result_frame(result)
    st.dataframe(frame, width="stretch", hide_index=True)
    over = [item for item in result["results"] if item["flag"] == "over_100"]
    if over:
        st.error(
            "Ada estimasi di atas 100%. Nilai tidak dipotong menjadi 100%; ini menandakan "
            "kapasitas target kemungkinan tidak memadai dengan asumsi beban tetap."
        )
    near = [item for item in result["results"] if item["flag"] == "near_threshold"]
    if near:
        st.warning(
            f"Ada estimasi yang mencapai/melampaui ambang peringatan "
            f"{number(result['warning_threshold_pct'], 1)}%."
        )

    st.markdown("**Biaya (jika harga tersedia)**")
    price = result["price"]
    source = price["source"]
    target = price["target"]
    if source:
        st.write(
            f"Harga sumber inventaris: {number(source['amount'], 2)} {source['currency']} "
            f"({PRICE_UNITS.get(source['unit'], source['unit'])}), "
            f"tanggal {source['source_date']}."
        )
    else:
        st.caption("Harga sumber belum tersedia di inventaris.")
    if target:
        st.write(
            f"Harga target input: {number(target['amount'], 2)} {target['currency']} "
            f"({PRICE_UNITS.get(target['unit'], target['unit'])}), "
            f"tanggal {target['source_date']}."
        )
    if price["difference"] is not None:
        st.info(
            f"Selisih harga input: {number(price['difference'], 2)} "
            f"{target['currency']} {PRICE_UNITS.get(target['unit'], target['unit']).lower()}."
        )
    else:
        st.info(price["message"])
    st.caption(
        "Selisih harga bukan estimasi penghematan bulanan. Tidak ada konversi mata uang dan "
        "tidak ada asumsi harga turun proporsional dengan ukuran instance."
    )

    with st.expander("Asumsi dan batasan estimasi"):
        for item in result["assumptions"]:
            st.write("- " + item)
        st.write("- Estimasi di atas 100% tidak dipotong.")
        st.write("- Ambang peringatan: " + number(result["warning_threshold_pct"], 1) + "%.")
        st.caption(
            "Aplikasi tidak mengeksekusi resize dan tidak terhubung ke API cloud. "
            "Hasil bukan rekomendasi otomatis."
        )


def _save_section(result: dict) -> None:
    st.subheader("Simpan simulasi")
    st.caption("Snapshot menyimpan input dan hasil estimasi untuk jejak audit.")
    price = result["price"]["target"] or {}
    with st.form(f"save_sim_{result['server_code']}_{result['target_vcpu']}_{result['target_ram_gib']}"):
        name = st.text_input("Nama simulasi *")
        notes = st.text_area("Catatan")
        submitted = st.form_submit_button("Simpan simulasi", type="primary")
    if submitted:
        try:
            saved = simulation_service.save_resize(
                result["analysis"], result["server_code"],
                result["target_vcpu"], result["target_ram_gib"],
                name=name,
                warning_threshold_pct=result["warning_threshold_pct"],
                target_instance_type=result["target_instance_type"],
                target_price_amount=price.get("amount"),
                target_price_currency=price.get("currency"),
                target_price_unit=price.get("unit"),
                target_price_unit_label=price.get("unit_label"),
                target_price_source_date=price.get("source_date"),
                notes=notes,
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.success(f"Simulasi #{saved['simulation_id']} disimpan.")


def _saved_section() -> None:
    st.subheader("Simulasi tersimpan")
    simulations = simulation_service.list_simulations()
    if not simulations:
        st.caption("Belum ada simulasi tersimpan.")
        return
    rows = [{
        "ID": item["id"],
        "Nama": item["name"],
        "Server": item["server_code"],
        "vCPU": f"{item['source_vcpu']} → {item['target_vcpu']}",
        "RAM GiB": f"{number(item['source_ram_gib'], 1)} → {number(item['target_ram_gib'], 1)}",
        "Ambang (%)": item["warning_threshold_pct"],
        "Data cukup": "Ya" if item["data_sufficient"] else "Tidak",
        "Dibuat": item["created_at"],
    } for item in simulations]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    normalize_selection("saved_sim_select", [item["id"] for item in simulations])
    selected_id = st.selectbox(
        "Detail simulasi", options=[item["id"] for item in simulations],
        format_func=lambda sim_id: f"#{sim_id}", key="saved_sim_select",
    )
    detail = simulation_service.get_simulation(selected_id)
    detail_rows = [{
        "Metrik": METRIC_LABELS.get(item["metric"], item["metric"]),
        "Statistik": MEASURE_LABELS.get(item["stat_name"], item["stat_name"]),
        "Sebelum (%)": item["before_value"],
        "Sesudah estimasi (%)": item["after_value"],
        "Status": ESTIMATE_FLAGS.get(item["flag"], item["flag"]),
    } for item in detail["results"]]
    st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)
    st.caption(
        "Simulasi tersimpan memuat harga target bila diisi. Snapshot harga sumber tidak disimpan; "
        "selisih harga tidak dihitung ulang."
    )
    confirm = st.checkbox(f"Saya yakin menghapus simulasi #{selected_id}", key="sim_delete_confirm")
    if st.button("Hapus simulasi", disabled=not confirm):
        simulation_service.delete_simulation(selected_id)
        st.success("Simulasi dihapus.")
        st.rerun()


def render(filters: dict | None) -> None:
    st.title("Simulator Resize")
    st.caption(
        "Estimasi sederhana dengan asumsi beban tetap. Tidak menjamin performa aplikasi dan "
        "bukan rekomendasi resize otomatis."
    )
    analysis = build_analysis(filters)
    if analysis is None:
        return
    included = [s for s in analysis.included_servers]
    if not included:
        st.info("Tidak ada server dalam scope.")
        return
    settings = settings_service.get_settings()
    normalize_selection("sim_server", [s.code for s in included])
    server_code = st.selectbox(
        "Server", options=[s.code for s in included],
        format_func=lambda code: next(
            f"{s.code} — {s.vcpu} vCPU / {number(s.ram_gib, 1)} GiB"
            for s in included if s.code == code
        ),
        key="sim_server",
    )
    server = next(s for s in included if s.code == server_code)
    _source_panel(analysis, server_code)

    st.subheader("Input kapasitas target")
    has_price = st.toggle(
        "Harga target tersedia", value=False, key=f"sim_has_price_{server_code}",
    )
    with st.form(f"sim_form_{server_code}"):
        col1, col2 = st.columns(2)
        target_vcpu = col1.number_input(
            "vCPU target *", min_value=1, value=int(server.vcpu), step=1,
            key=f"sim_target_vcpu_{server_code}",
        )
        target_ram = col2.number_input(
            "RAM target GiB *", min_value=0.1, value=float(server.ram_gib), step=0.5,
            key=f"sim_target_ram_{server_code}",
        )
        threshold = st.number_input(
            "Ambang peringatan (%)", min_value=0.1, max_value=100.0,
            value=float(settings["warning_threshold_pct"]), step=1.0,
            key=f"sim_threshold_{server_code}",
        )
        instance_type = st.text_input(
            "Tipe instance target (opsional)", key=f"sim_instance_{server_code}",
            help="Belum tervalidasi; aplikasi tidak memeriksa katalog instance.",
        )
        price_values = {}
        if has_price:
            st.markdown("**Harga target (opsional)**")
            price_values["amount"] = st.number_input(
                "Harga target", min_value=0.0, value=0.0, step=0.01, format="%.2f",
                key=f"sim_price_amount_{server_code}",
            )
            price_values["currency"] = st.text_input(
                "Mata uang (3 huruf)", max_chars=3, key=f"sim_price_currency_{server_code}"
            )
            price_values["unit"] = st.selectbox(
                "Satuan harga", options=list(PRICE_UNITS),
                format_func=lambda value: PRICE_UNITS[value],
                key=f"sim_price_unit_{server_code}",
            )
            price_values["unit_label"] = st.text_input(
                "Label satuan Lainnya", key=f"sim_price_label_{server_code}"
            )
            price_values["source_date"] = st.date_input(
                "Tanggal sumber harga", value=date.today(),
                key=f"sim_price_date_{server_code}",
            ).isoformat()
        submitted = st.form_submit_button("Hitung estimasi", type="primary")
    if submitted:
        try:
            result = simulation_service.compute_resize(
                analysis, server_code, target_vcpu, target_ram,
                warning_threshold_pct=threshold,
                target_instance_type=instance_type,
                target_price_amount=price_values.get("amount"),
                target_price_currency=price_values.get("currency"),
                target_price_unit=price_values.get("unit"),
                target_price_unit_label=price_values.get("unit_label"),
                target_price_source_date=price_values.get("source_date"),
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            result["analysis"] = analysis
            st.session_state["sim_result"] = result

    result = st.session_state.get("sim_result")
    if result and result.get("server_code") == server_code:
        _show_result(result)
        _save_section(result)

    st.divider()
    _saved_section()
