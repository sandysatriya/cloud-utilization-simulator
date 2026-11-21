import streamlit as st

from cloudsim.config import APP_NAME, APP_VERSION, STAT_DISCLAIMER

PAGE_IMPORT = "import"
PAGE_INVENTORY = "inventory"
PAGE_DASHBOARD = "dashboard"
PAGE_COMPARISON = "comparison"
PAGE_SIMULATOR = "simulator"
PAGE_KPI = "kpi"
PAGE_EXPORT = "export"

PAGES = [
    (PAGE_IMPORT, "Import & Validasi"),
    (PAGE_INVENTORY, "Inventaris & Scope"),
    (PAGE_DASHBOARD, "Dashboard Utilization"),
    (PAGE_COMPARISON, "Perbandingan & Baseline"),
    (PAGE_SIMULATOR, "Simulator Resize"),
    (PAGE_KPI, "Konfigurasi KPI"),
    (PAGE_EXPORT, "Export Excel"),
]


def render_navigation() -> str:
    st.sidebar.title("Cloud Utilization")
    st.sidebar.caption("Simulator rightsizing lokal")
    labels = dict(PAGES)
    page = st.sidebar.radio(
        "Navigasi",
        options=[key for key, _ in PAGES],
        format_func=lambda key: labels[key],
        key="nav_page",
    )
    st.sidebar.divider()
    st.sidebar.caption(f"{APP_NAME} v{APP_VERSION}")
    st.sidebar.caption(STAT_DISCLAIMER)
    return page
