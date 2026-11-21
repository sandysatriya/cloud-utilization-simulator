import pandas as pd
import streamlit as st

from cloudsim.enums import QUALITY_FLAGS
from cloudsim.errors import AppError
from cloudsim.services import baseline_service
from cloudsim.ui.context import build_analysis, normalize_selection
from cloudsim.ui.format import local_range, number, pp, relative


METRIC_LABELS = {"cpu": "CPU", "memory": "Memory"}


def _create_section(analysis) -> None:
    st.subheader("Buat snapshot baseline")
    st.caption(
        "Snapshot menyimpan daftar server, periode, statistik, pengecualian, sumber batch, "
        "dan versi formula. Baseline tidak berubah saat batch dihapus atau scope diubah."
    )
    with st.form("create_baseline_form", clear_on_submit=True):
        name = st.text_input("Nama baseline *")
        notes = st.text_area("Catatan")
        submitted = st.form_submit_button("Simpan baseline", type="primary")
    if submitted:
        try:
            baseline_id = baseline_service.create_baseline(name, analysis, notes)
        except AppError as exc:
            st.error(str(exc))
        else:
            st.success(f"Baseline #{baseline_id} disimpan.")
            st.session_state["baseline_select"] = baseline_id
            st.rerun()


def _comparison_frame(comparison: dict) -> pd.DataFrame:
    rows = []
    for item in comparison["rows"]:
        row = {
            "Kode": item["server_code"],
            "Metrik": METRIC_LABELS.get(item["metric"], item["metric"]),
            "Di baseline": "Ya" if item["in_baseline"] else "Tidak",
            "Di periode ini": "Ya" if item["in_current"] else "Tidak",
        }
        for stat, label in (("avg", "Rata-rata"), ("p95", "P95"), ("max", "Maksimum")):
            row[f"{label} baseline"] = number(item["before"][stat])
            row[f"{label} sekarang"] = number(item["after"][stat])
            row[f"Δ {label} (pp)"] = pp(item["delta"][stat]["pp"])
            row[f"Δ {label} (%)"] = relative(item["delta"][stat]["relative_pct"])
        row["Sampel baseline"] = item["before_samples"]
        row["Sampel sekarang"] = item["after_samples"]
        row["Kelengkapan baseline"] = number(item["before_completeness"], 1)
        row["Kelengkapan sekarang"] = number(item["after_completeness"], 1)
        row["Flag baseline"] = ", ".join(
            QUALITY_FLAGS.get(flag, flag) for flag in item["before_flags"]
        ) or "Tidak ada"
        row["Flag sekarang"] = ", ".join(
            QUALITY_FLAGS.get(flag, flag) for flag in item["after_flags"]
        ) or "Tidak ada"
        rows.append(row)
    return pd.DataFrame(rows)


def _show_comparison(comparison: dict) -> None:
    if not comparison["comparable"]:
        st.error(
            "Metadata sumber berbeda. Delta ditampilkan untuk transparansi, tetapi "
            "perbandingan tidak sepenuhnya setara."
        )
    else:
        st.success("Metadata sumber utama sama.")
    if comparison["scope_added"] or comparison["scope_removed"]:
        st.warning(
            "Scope berubah. Server masuk: "
            + (", ".join(comparison["scope_added"]) or "-")
            + "; server keluar: "
            + (", ".join(comparison["scope_removed"]) or "-")
        )
    if comparison["exclusion_added"] or comparison["exclusion_removed"] or comparison["exclusion_changed"]:
        st.warning(
            "Pengecualian berubah. Baru: "
            + (", ".join(comparison["exclusion_added"]) or "-")
            + "; dihapus: "
            + (", ".join(comparison["exclusion_removed"]) or "-")
            + "; alasan berubah: "
            + (", ".join(comparison["exclusion_changed"]) or "-")
        )
    if comparison["metadata_changes"]:
        st.markdown("**Perbedaan metadata**")
        for item in comparison["metadata_changes"]:
            st.write("- " + item)
    if comparison["inventory_changes"]:
        st.markdown("**Perubahan inventaris**")
        for item in comparison["inventory_changes"]:
            st.write("- " + item)
    if comparison["quality_changes"]:
        st.markdown("**Perubahan kualitas data**")
        for item in comparison["quality_changes"]:
            st.write("- " + item)

    st.markdown("**Delta per server**")
    frame = _comparison_frame(comparison)
    if frame.empty:
        st.info("Tidak ada data untuk dibandingkan.")
    else:
        st.dataframe(frame, width="stretch", hide_index=True)
    st.caption(
        "Δ (pp) adalah selisih percentage point. Δ (%) adalah perubahan relatif terhadap nilai "
        "baseline dan tidak dihitung bila baseline 0 atau tidak tersedia. Keduanya bukan ukuran "
        "yang sama."
    )


def render(filters: dict | None) -> None:
    st.title("Perbandingan Periode & Baseline")
    st.caption(
        "Bandingkan periode analisis saat ini dengan snapshot baseline. Perubahan scope dan "
        "kualitas data selalu ditandai."
    )
    analysis = build_analysis(filters)
    if analysis is None:
        return
    st.markdown(
        f"**Periode saat ini:** "
        f"{local_range(analysis.window_start_utc, analysis.window_end_utc, analysis.display_timezone)}"
    )
    _create_section(analysis)

    baselines = baseline_service.list_baselines()
    if not baselines:
        st.info("Belum ada baseline. Buat snapshot setelah periode dan scope dinyatakan layak.")
        return

    st.subheader("Baseline tersimpan")
    rows = [{
        "ID": item["id"],
        "Nama": item["name"],
        "Dibuat": item["created_at"],
        "Periode": local_range(
            item["window_start_utc"], item["window_end_utc"], item["display_timezone"]
        ),
        "Jumlah server": item["server_count"],
        "Versi formula": item["formula_version"],
        "Catatan": item["notes"],
    } for item in baselines]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    normalize_selection("baseline_select", [item["id"] for item in baselines])
    selected_id = st.selectbox(
        "Pilih baseline untuk dibandingkan",
        options=[item["id"] for item in baselines],
        format_func=lambda baseline_id: next(
            f"#{b['id']} {b['name']}" for b in baselines if b["id"] == baseline_id
        ),
        key="baseline_select",
    )
    try:
        comparison = baseline_service.compare(selected_id, analysis)
    except AppError as exc:
        st.error(str(exc))
        return
    st.markdown(
        f"**Baseline:** {comparison['baseline_name']} | "
        f"dibuat {comparison['baseline_created_at']} | "
        f"formula {comparison['baseline_formula_version']}"
    )
    _show_comparison(comparison)

    st.divider()
    st.subheader("Hapus baseline")
    st.caption("Snapshot baseline tidak memengaruhi data time series. Penghapusan tidak dapat dibatalkan.")
    confirm = st.checkbox(
        f"Saya yakin menghapus baseline #{selected_id}", key="baseline_delete_confirm"
    )
    if st.button("Hapus baseline", disabled=not confirm):
        baseline_service.delete_baseline(selected_id)
        st.success("Baseline dihapus.")
        st.rerun()
