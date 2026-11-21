from pathlib import Path

from streamlit.testing.v1 import AppTest

from cloudsim.services import (
    baseline_service,
    kpi_service,
    simulation_service,
)
from cloudsim.ui.navigation import PAGES

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"

PAGE_TITLES = {
    "import": "Import & Validasi Data",
    "inventory": "Inventaris & Pengaturan Scope",
    "dashboard": "Dashboard Utilization",
    "comparison": "Perbandingan Periode & Baseline",
    "simulator": "Simulator Resize",
    "kpi": "Konfigurasi KPI",
    "export": "Export Excel",
}


def _seed_ui_extras(dataset):
    baseline_service.create_baseline(
        "Baseline UI", dataset.analysis, db_path=dataset.db_path
    )
    kpi_service.save_definition({
        "name": "CPU P95 UI",
        "metric": "cpu",
        "measure": "p95",
        "aggregate_method": "capacity_weighted_vcpu",
        "operator": "lte",
        "target_value": 60,
        "target_value_upper": None,
        "scope_mode": "current_scope",
        "baseline_id": None,
    }, approve=True, db_path=dataset.db_path)
    simulation_service.save_resize(
        dataset.analysis, "SRV-A", 2, 4,
        name="Simulasi UI",
        warning_threshold_pct=80,
        db_path=dataset.db_path,
    )


def _assert_clean(at):
    assert not at.exception, [str(item) for item in at.exception]


def _navigate(at, page):
    at.sidebar.radio[0].set_value(page).run(timeout=60)
    _assert_clean(at)
    assert any(item.value == PAGE_TITLES[page] for item in at.title), page


def test_all_pages_render_without_exceptions(dataset, monkeypatch):
    monkeypatch.setenv("CLOUDSIM_DB_PATH", str(dataset.db_path))
    _seed_ui_extras(dataset)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    _assert_clean(at)
    for page, _label in PAGES:
        _navigate(at, page)


def test_simulator_form_computes_and_export_button_produces_download(dataset, monkeypatch):
    monkeypatch.setenv("CLOUDSIM_DB_PATH", str(dataset.db_path))
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    _navigate(at, "simulator")

    server_select = next(item for item in at.selectbox if item.label == "Server")
    server_select.set_value("SRV-A").run(timeout=60)
    _assert_clean(at)

    vcpu_input = next(
        item for item in at.number_input if item.label.startswith("vCPU target")
    )
    vcpu_input.set_value(2).run(timeout=60)
    submit = next(
        item for item in at.form_submit_button if item.label == "Hitung estimasi"
    )
    submit.click().run(timeout=60)
    _assert_clean(at)
    assert any(item.value == "Hasil estimasi" for item in at.subheader)

    _navigate(at, "export")
    export_button = next(
        item for item in at.button if item.label == "Buat file Excel"
    )
    export_button.click().run(timeout=60)
    _assert_clean(at)
    assert len(at.download_button) == 1
