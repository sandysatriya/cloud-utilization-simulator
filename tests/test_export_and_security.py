import ast
import io
import socket
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from cloudsim.errors import ValidationError
from cloudsim.io.excel_writer import safe_sheet_name, workbook_bytes
from cloudsim.io.sanitize import DANGEROUS_PREFIXES, sanitize_text
from cloudsim.services import batch_service, export_service, simulation_service
from cloudsim.services.analysis_service import analyze
from tests.helpers import END, START, add_server, add_time_batch, series

ROOT = Path(__file__).resolve().parent.parent


def _malicious_analysis(db_path):
    add_server(
        db_path,
        "SRV-X",
        name='+HYPERLINK("http://example.invalid","klik")',
        workload="@SUM(1,1)",
        region="+1+1",
        notes="-2+3",
    )
    add_time_batch(db_path, "cpu", {"SRV-X": series(START, [10, 20, 30, 40])})
    add_time_batch(db_path, "memory", {"SRV-X": series(START, [80, 85, 90, 95])})
    cpu_batch = next(b.id for b in batch_service.list_batches("cpu", db_path=db_path))
    memory_batch = next(
        b.id for b in batch_service.list_batches("memory", db_path=db_path)
    )
    return analyze(START, END, [cpu_batch], [memory_batch], "UTC", db_path=db_path)


def _kpi_definitions():
    return [{
        "id": 1,
        "name": "-2+3",
        "description": "\t=cmd|' /C calc'!A0",
        "status": "approved",
        "metric": "cpu",
        "measure": "p95",
        "aggregate_method": "simple_mean",
        "operator": "lte",
        "target_value": 50,
        "target_value_upper": None,
        "scope_mode": "current_scope",
        "baseline_id": None,
        "approved_at": "2026-11-22T00:00:00Z",
        "formula_version": "kpi-config-v1",
    }]


def test_sanitize_text_prefixes_all_dangerous_leads():
    for value in ("=1+1", "+1", "-1", "@x", "\tx", "\rx"):
        assert sanitize_text(value) == "'" + value
    assert sanitize_text("teks aman") == "teks aman"
    assert sanitize_text(123) == 123


def test_workbook_sanitizes_headers_values_and_sheet_names():
    df = pd.DataFrame([{"=header": "=1+1", "normal": "+2+2"}])
    data = workbook_bytes([("bad[name]:*?/\\" * 4, df)])
    wb = load_workbook(io.BytesIO(data))
    ws = wb.worksheets[0]
    assert len(ws.title) <= 31
    assert not any(ch in ws.title for ch in "[]:*?/\\")
    for row in ws.iter_rows():
        for cell in row:
            assert cell.data_type != "f"
            if isinstance(cell.value, str):
                assert not cell.value.startswith(DANGEROUS_PREFIXES)
    assert wb.vba_archive is None
    assert list(wb._external_links) == []


def test_export_contains_no_formula_injection_or_raw_samples_by_default(db_path):
    analysis = _malicious_analysis(db_path)
    simulation = simulation_service.compute_resize(
        analysis, "SRV-X", 2, 4, warning_threshold_pct=80, db_path=db_path
    )
    simulation["name"] = "-simulasi"
    data = export_service.build_export(
        analysis, simulation=simulation, kpi_definitions=_kpi_definitions()
    )
    wb = load_workbook(io.BytesIO(data))
    names = wb.sheetnames
    assert len(names) == 10
    assert not any(name.startswith("Data Mentah") for name in names)
    assert "KPI per Server" not in names
    assert "Statistik Server" in names
    assert wb.vba_archive is None
    assert list(wb._external_links) == []

    found_sanitized = set()
    for ws in wb.worksheets:
        assert len(ws.title) <= 31
        assert not any(ch in ws.title for ch in "[]:*?/\\")
        for row in ws.iter_rows():
            for cell in row:
                assert cell.data_type != "f"
                if isinstance(cell.value, str):
                    assert not cell.value.startswith(DANGEROUS_PREFIXES)
                    if cell.value.startswith("'"):
                        found_sanitized.add(cell.value)
    assert any(value.startswith("'+") for value in found_sanitized)
    assert any(value.startswith("'@") for value in found_sanitized)
    assert any(value.startswith("'-") for value in found_sanitized)
    assert any(value.startswith("'\t") for value in found_sanitized)

    stats = wb["Statistik Server"]
    assert stats.max_row <= 1 + len(analysis.stats)

    kpi = wb["KPI"]
    kpi_headers = [cell.value for cell in kpi[1]]
    assert kpi[2][kpi_headers.index("Perhitungan")].value == export_service.KPI_NOT_COMPUTED
    assert not {"Nilai agregat", "Lulus"} & set(kpi_headers)


def test_export_includes_raw_samples_when_requested(db_path):
    analysis = replace(_malicious_analysis(db_path), display_timezone="Asia/Jakarta")
    data = export_service.build_export(analysis, include_raw_samples=True)
    wb = load_workbook(io.BytesIO(data))
    assert wb.sheetnames[-2:] == ["Data Mentah CPU", "Data Mentah Memory"]

    cpu = list(wb["Data Mentah CPU"].iter_rows(values_only=True))
    assert cpu[0] == (
        "Kode server", "Metrik", "Waktu tampilan (Asia/Jakarta)", "Waktu UTC", "Nilai (%)"
    )
    assert cpu[1] == ("SRV-X", "CPU", "2026-01-01 07:00:00+07:00", "2026-01-01 00:00:00+00:00", 10)
    assert [row[4] for row in cpu[1:]] == [10, 20, 30, 40]
    memory = list(wb["Data Mentah Memory"].iter_rows(values_only=True))
    assert [row[4] for row in memory[1:]] == [80, 85, 90, 95]
    summary = {row[0]: row[1] for row in wb["Ringkasan"].iter_rows(values_only=True)}
    assert summary["Data sampel mentah"].startswith("Disertakan")


def test_raw_sample_export_rejects_more_rows_than_excel_allows(db_path, monkeypatch):
    analysis = _malicious_analysis(db_path)
    monkeypatch.setattr(export_service, "EXCEL_MAX_DATA_ROWS", 3)
    with pytest.raises(ValidationError, match="batas Excel"):
        export_service.build_export(analysis, include_raw_samples=True)
    assert export_service.build_export(analysis)[:2] == b"PK"


def test_safe_sheet_name_deduplicates():
    used: set[str] = set()
    assert safe_sheet_name("Nama/Sheet", used) == "NamaSheet"
    assert safe_sheet_name("Nama/Sheet", used) == "NamaSheet_2"


def test_sources_do_not_import_network_cloud_or_process_libraries():
    forbidden = {
        "requests", "httpx", "urllib", "urllib3", "http", "socket",
        "boto3", "botocore", "googleapiclient", "azure", "paramiko",
        "subprocess",
    }
    paths = list((ROOT / "cloudsim").rglob("*.py"))
    paths.extend([ROOT / "app.py", *list((ROOT / "scripts").rglob("*.py"))])
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not (roots & forbidden), f"{path} imports {roots & forbidden}"


def test_sources_do_not_use_eval_or_exec():
    paths = list((ROOT / "cloudsim").rglob("*.py"))
    paths.extend([ROOT / "app.py", *list((ROOT / "scripts").rglob("*.py"))])
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "compile"}, str(path)


def test_backend_flows_do_not_open_network_sockets(dataset, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Network call attempted")

    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)

    analysis = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    simulation_service.compute_resize(
        analysis, "SRV-A", 2, 4, db_path=dataset.db_path
    )
    data = export_service.build_export(analysis)
    assert data[:2] == b"PK"
