import streamlit as st

from cloudsim.config import APP_NAME
from cloudsim.db.migrate import migrate
from cloudsim.ui import context, navigation
from cloudsim.ui.views import (
    comparison,
    dashboard,
    export_view,
    import_data,
    inventory,
    kpi_config,
    simulator,
)


VIEWS = {
    navigation.PAGE_IMPORT: import_data.render,
    navigation.PAGE_INVENTORY: inventory.render,
    navigation.PAGE_DASHBOARD: dashboard.render,
    navigation.PAGE_COMPARISON: comparison.render,
    navigation.PAGE_SIMULATOR: simulator.render,
    navigation.PAGE_KPI: kpi_config.render,
    navigation.PAGE_EXPORT: export_view.render,
}


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon=None, layout="wide")
    try:
        migrate()
    except Exception as exc:
        st.error(f"Gagal menyiapkan database lokal: {exc}")
        st.stop()

    page = navigation.render_navigation()
    filters = context.render_filters()
    VIEWS[page](filters)


if __name__ == "__main__":
    main()
