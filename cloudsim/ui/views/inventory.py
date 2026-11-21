from datetime import date

import pandas as pd
import streamlit as st

from cloudsim.enums import PRICE_UNITS, SCOPE_DIMENSIONS, SCOPE_STATUS
from cloudsim.errors import AppError
from cloudsim.io.parsers import validate_timezone
from cloudsim.services import inventory_service, scope_service, settings_service
from cloudsim.ui.context import normalize_selection
from cloudsim.ui.format import number


def _price_fields(prefix: str, server=None) -> dict:
    amount = st.number_input(
        "Harga", min_value=0.0, value=float(server.price_amount or 0.0) if server else 0.0,
        step=0.01, format="%.2f", key=f"{prefix}_price_amount",
    )
    currency = st.text_input(
        "Mata uang (3 huruf)", value=(server.price_currency if server else "") or "",
        max_chars=3, key=f"{prefix}_price_currency",
    )
    unit = st.selectbox(
        "Satuan harga", options=list(PRICE_UNITS),
        format_func=lambda value: PRICE_UNITS[value],
        index=list(PRICE_UNITS).index(server.price_unit) if server and server.price_unit else 0,
        key=f"{prefix}_price_unit",
    )
    unit_label = st.text_input(
        "Label satuan Lainnya", value=(server.price_unit_label if server else "") or "",
        key=f"{prefix}_price_label",
    )
    source_date = st.date_input(
        "Tanggal sumber harga", value=date.fromisoformat(server.price_source_date)
        if server and server.price_source_date else date.today(),
        key=f"{prefix}_price_date",
    )
    return {
        "price_amount": amount,
        "price_currency": currency,
        "price_unit": unit,
        "price_unit_label": unit_label,
        "price_source_date": source_date.isoformat(),
    }


def _server_payload(prefix: str, server=None, has_price: bool = False) -> dict:
    code = st.text_input(
        "ID server *", value=(server.code if server else ""), key=f"{prefix}_code",
    )
    name = st.text_input("Nama/alias", value=(server.name if server else "") or "",
                         key=f"{prefix}_name")
    environment = st.text_input(
        "Environment *", value=(server.environment if server else ""), key=f"{prefix}_env",
    )
    region = st.text_input("Region", value=(server.region if server else "") or "",
                           key=f"{prefix}_region")
    workload = st.text_input("Workload", value=(server.workload if server else "") or "",
                             key=f"{prefix}_workload")
    vcpu = st.number_input(
        "vCPU *", min_value=1, step=1,
        value=int(server.vcpu) if server else 2, key=f"{prefix}_vcpu",
    )
    ram = st.number_input(
        "RAM GiB *", min_value=0.1, step=0.5,
        value=float(server.ram_gib) if server else 4.0, key=f"{prefix}_ram",
    )
    instance_type = st.text_input(
        "Tipe instance", value=(server.instance_type if server else "") or "",
        key=f"{prefix}_instance",
    )
    scope = st.selectbox(
        "Status scope", options=list(SCOPE_STATUS),
        format_func=lambda value: SCOPE_STATUS[value],
        index=list(SCOPE_STATUS).index(server.scope_status) if server else 0,
        key=f"{prefix}_scope",
    )
    reason = st.text_input(
        "Alasan pengecualian", value=(server.exclusion_reason if server else "") or "",
        key=f"{prefix}_reason",
        help="Wajib bila status Dikecualikan.",
    )
    notes = st.text_area("Catatan", value=(server.notes if server else "") or "",
                         key=f"{prefix}_notes")
    if has_price:
        price = _price_fields(prefix, server)
    else:
        price = {
            "price_amount": None, "price_currency": None, "price_unit": None,
            "price_unit_label": None, "price_source_date": None,
        }
    return {
        "server_code": code,
        "name": name,
        "environment": environment,
        "region": region,
        "workload": workload,
        "vcpu": vcpu,
        "ram_gib": ram,
        "instance_type": instance_type,
        "scope_status": scope,
        "exclusion_reason": reason,
        "notes": notes,
        **price,
    }


def _render_servers() -> None:
    st.subheader("Inventaris server")
    servers = inventory_service.list_servers()
    if servers:
        rows = []
        for server in servers:
            rows.append({
                "Kode": server.code,
                "Nama": server.name,
                "Environment": server.environment,
                "Region": server.region,
                "Workload": server.workload,
                "vCPU": server.vcpu,
                "RAM GiB": server.ram_gib,
                "Tipe instance": server.instance_type,
                "Scope": SCOPE_STATUS.get(server.scope_status, server.scope_status),
                "Alasan pengecualian": server.exclusion_reason,
                "Harga": number(server.price_amount, 2) if server.price_amount is not None else "—",
                "Mata uang": server.price_currency,
                "Satuan": PRICE_UNITS.get(server.price_unit, server.price_unit),
                "Tanggal harga": server.price_source_date,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Belum ada server. Tambahkan manual atau impor inventaris.")

    with st.expander("Tambah server manual"):
        has_price = st.toggle(
            "Harga sumber tersedia", value=False, key="add_has_price",
            help="Harga opsional. Jika diisi, semua field harga dan tanggal sumber wajib lengkap.",
        )
        with st.form("add_server_form", clear_on_submit=True):
            payload = _server_payload("add", has_price=has_price)
            submitted = st.form_submit_button("Tambah server", type="primary")
        if submitted:
            try:
                inventory_service.create_server(payload)
            except AppError as exc:
                st.error(str(exc))
            else:
                st.success("Server ditambahkan.")
                st.rerun()

    if servers:
        with st.expander("Ubah server"):
            normalize_selection("edit_server_select", [s.id for s in servers])
            selected_id = st.selectbox(
                "Pilih server", options=[s.id for s in servers],
                format_func=lambda server_id: next(
                    s.code for s in servers if s.id == server_id
                ),
                key="edit_server_select",
            )
            selected = next(s for s in servers if s.id == selected_id)
            has_price = st.toggle(
                "Harga sumber tersedia",
                value=selected.price_amount is not None,
                key=f"edit_has_price_{selected_id}",
            )
            with st.form(f"edit_server_form_{selected_id}"):
                payload = _server_payload(f"edit_{selected_id}", selected, has_price)
                submitted = st.form_submit_button("Simpan perubahan", type="primary")
            if submitted:
                try:
                    inventory_service.update_server(selected_id, payload)
                except AppError as exc:
                    st.error(str(exc))
                else:
                    st.success("Perubahan disimpan.")
                    st.rerun()

        with st.expander("Hapus server"):
            st.caption(
                "Server yang sudah memiliki data time series tidak dapat dihapus; "
                "gunakan status Dikecualikan agar data dan alasannya tetap tercatat."
            )
            normalize_selection("delete_server_select", [s.id for s in servers])
            selected_id = st.selectbox(
                "Pilih server", options=[s.id for s in servers],
                format_func=lambda server_id: next(
                    s.code for s in servers if s.id == server_id
                ),
                key="delete_server_select",
            )
            confirm = st.checkbox("Saya yakin menghapus server ini", key="delete_server_confirm")
            if st.button("Hapus server", disabled=not confirm):
                try:
                    inventory_service.delete_server(selected_id)
                except AppError as exc:
                    st.error(str(exc))
                else:
                    st.success("Server dihapus.")
                    st.rerun()


def _render_rules() -> None:
    st.subheader("Aturan scope")
    st.caption(
        "Server dikecualikan bila memenuhi salah satu aturan aktif ATAU ditandai Dikecualikan "
        "secara manual. Alasan wajib diisi. Aturan disimpan sebagai konfigurasi, bukan hardcode."
    )
    rules = scope_service.list_rules()
    if rules:
        rows = [{
            "ID": rule["id"],
            "Nama": rule["name"],
            "Dimensi": SCOPE_DIMENSIONS.get(rule["dimension"], rule["dimension"]),
            "Nilai": rule["match_value"],
            "Alasan": rule["reason"],
            "Aktif": "Ya" if rule["active"] else "Tidak",
        } for rule in rules]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Belum ada aturan scope.")

    with st.expander("Tambah aturan"):
        with st.form("add_rule_form", clear_on_submit=True):
            name = st.text_input("Nama aturan *")
            dimension = st.selectbox(
                "Dimensi *", options=list(SCOPE_DIMENSIONS),
                format_func=lambda value: SCOPE_DIMENSIONS[value],
            )
            match_value = st.text_input("Nilai yang dicocokkan *")
            reason = st.text_input("Alasan pengecualian *")
            active = st.checkbox("Aktif", value=True)
            submitted = st.form_submit_button("Tambah aturan", type="primary")
        if submitted:
            try:
                scope_service.create_rule({
                    "name": name, "dimension": dimension, "match_value": match_value,
                    "reason": reason, "active": active,
                })
            except AppError as exc:
                st.error(str(exc))
            else:
                st.success("Aturan ditambahkan.")
                st.rerun()

    if rules:
        with st.expander("Ubah / hapus aturan"):
            normalize_selection("rule_select", [rule["id"] for rule in rules])
            selected_id = st.selectbox(
                "Pilih aturan", options=[rule["id"] for rule in rules],
                format_func=lambda rule_id: next(
                    r["name"] for r in rules if r["id"] == rule_id
                ),
                key="rule_select",
            )
            selected = next(r for r in rules if r["id"] == selected_id)
            affected = scope_service.affected_servers(selected)
            st.caption("Server terdampak: " + (", ".join(affected) if affected else "(tidak ada)"))
            with st.form(f"edit_rule_form_{selected_id}"):
                name = st.text_input("Nama aturan *", value=selected["name"],
                                     key=f"rule_name_{selected_id}")
                dimension = st.selectbox(
                    "Dimensi *", options=list(SCOPE_DIMENSIONS),
                    format_func=lambda value: SCOPE_DIMENSIONS[value],
                    index=list(SCOPE_DIMENSIONS).index(selected["dimension"]),
                    key=f"rule_dimension_{selected_id}",
                )
                match_value = st.text_input("Nilai yang dicocokkan *", value=selected["match_value"],
                                            key=f"rule_match_{selected_id}")
                reason = st.text_input("Alasan pengecualian *", value=selected["reason"],
                                       key=f"rule_reason_{selected_id}")
                active = st.checkbox("Aktif", value=bool(selected["active"]),
                                     key=f"rule_active_{selected_id}")
                submitted = st.form_submit_button("Simpan aturan", type="primary")
            if submitted:
                try:
                    scope_service.update_rule(selected_id, {
                        "name": name, "dimension": dimension, "match_value": match_value,
                        "reason": reason, "active": active,
                    })
                except AppError as exc:
                    st.error(str(exc))
                else:
                    st.success("Aturan disimpan.")
                    st.rerun()
            confirm = st.checkbox("Saya yakin menghapus aturan ini", key="rule_delete_confirm")
            if st.button("Hapus aturan", disabled=not confirm):
                scope_service.delete_rule(selected_id)
                st.success("Aturan dihapus.")
                st.rerun()

    exclusions = scope_service.effective_exclusions_list()
    st.markdown("**Pengecualian efektif**")
    if exclusions:
        st.dataframe(pd.DataFrame([{
            "Kode server": item.server_code,
            "Nama": item.server_name,
            "Sumber": "Manual" if item.source == "manual" else "Aturan",
            "Aturan": item.rule_name,
            "Alasan": item.reason,
        } for item in exclusions]), width="stretch", hide_index=True)
    else:
        st.caption("Tidak ada server yang dikecualikan.")


def _render_settings() -> None:
    st.subheader("Ambang dan tampilan")
    settings = settings_service.get_settings()
    with st.form("settings_form"):
        display_tz = st.text_input(
            "Zona waktu tampilan", value=settings["display_timezone"],
            help="Contoh Asia/Jakarta. Metadata zona waktu sumber tetap disimpan per batch.",
        )
        warning = st.number_input(
            "Ambang peringatan estimasi (%)", min_value=0.1, max_value=100.0,
            value=float(settings["warning_threshold_pct"]), step=1.0,
            help="Estimasi di atas ambang ini ditandai mendekati ambang; di atas 100% tetap peringatan.",
        )
        completeness = st.number_input(
            "Kelengkapan minimum (%)", min_value=0.0, max_value=100.0,
            value=float(settings["min_completeness_pct"]), step=1.0,
        )
        min_samples = st.number_input(
            "Jumlah sampel minimum", min_value=1, value=int(settings["min_samples"]), step=1,
        )
        submitted = st.form_submit_button("Simpan pengaturan", type="primary")
    if submitted:
        try:
            validate_timezone(display_tz)
            settings_service.update_thresholds(
                float(warning), float(completeness), int(min_samples), display_tz.strip()
            )
        except AppError as exc:
            st.error(str(exc))
        else:
            st.success("Pengaturan disimpan.")
            st.rerun()


def render(_filters: dict | None = None) -> None:
    st.title("Inventaris & Pengaturan Scope")
    st.caption(
        "Inventaris adalah sumber kapasitas dan harga. Pengecualian scope memengaruhi analisis, "
        "baseline, simulasi, dan KPI."
    )
    tab_servers, tab_rules, tab_settings = st.tabs(
        ["Server", "Scope & Pengecualian", "Ambang & Tampilan"]
    )
    with tab_servers:
        _render_servers()
    with tab_rules:
        _render_rules()
    with tab_settings:
        _render_settings()
