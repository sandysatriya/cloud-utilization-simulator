import ast
import io
import socket
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

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


def _kpi_results():
    return [{
        "definition": {
            "id": 1,
            "name": "-2+3",
            "status": "approved",
            "metric": "cpu",
            "measure": "p95",
            "aggregate_method": "simple_mean",
            "operator": "lte",
            "target_value": 50,
            "target_value_upper": None,
            "scope_mode": "current_scope",
            "baseline_id": None,
        },
        "evaluation": {
            "available": True,
            "aggregate_value": 38.5,
            "total_count": 1,
            "passed_count": None,
            "evaluated": True,
            "reason": "\t=cmd|' /C calc'!A0",
            "formula_version": "kpi-config-v1",
            "per_server": [{"server_code": "SRV-X", "value": 38.5}],
        },
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


def test_export_contains_no_formula_injection_or_raw_samples(db_path):
    analysis = _malicious_analysis(db_path)
    simulation = simulation_service.compute_resize(
        analysis, "SRV-X", 2, 4, warning_threshold_pct=80, db_path=db_path
    )
    simulation["name"] = "-simulasi"
    data = export_service.build_export(
        analysis, simulation=simulation, kpi_results=_kpi_results()
    )
    wb = load_workbook(io.BytesIO(data))
    names = wb.sheetnames
    assert len(names) == 11
    assert "Sampel" not in names
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
