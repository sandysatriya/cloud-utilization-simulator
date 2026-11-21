import pytest

from cloudsim.errors import NotFoundError, ValidationError
from cloudsim.services import (
    batch_service,
    baseline_service,
    inventory_service,
    scope_service,
    settings_service,
)
from cloudsim.services.analysis_service import analyze
from tests.helpers import (
    END,
    START,
    add_server,
    add_time_batch,
    series,
    server_data,
)


def _update_server(db_path, code, **overrides):
    server = next(
        s for s in inventory_service.list_servers(db_path=db_path) if s.code == code
    )
    data = server_data(
        server.code,
        name=server.name,
        environment=server.environment,
        region=server.region,
        workload=server.workload,
        vcpu=server.vcpu,
        ram_gib=server.ram_gib,
        scope_status=server.scope_status,
        exclusion_reason=server.exclusion_reason,
    )
    data.update(overrides)
    inventory_service.update_server(server.id, data, db_path=db_path)


def test_manual_and_rule_exclusions_are_recorded_with_reasons(dataset):
    scope_service.create_rule({
        "name": "Kecualikan workload web",
        "dimension": "workload",
        "match_value": "web",
        "reason": "Aplikasi web belum termasuk gelombang rightsizing.",
    }, db_path=dataset.db_path)
    _update_server(
        dataset.db_path, "SRV-B",
        scope_status="excluded", exclusion_reason="Database legacy tanpa monitoring memadai.",
    )

    analysis = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    assert analysis.included_servers == []
    by_code = {item.server_code: item for item in analysis.exclusions}
    assert by_code["SRV-A"].source == "rule"
    assert by_code["SRV-A"].reason.startswith("Aplikasi web")
    assert by_code["SRV-B"].source == "manual"
    assert by_code["SRV-B"].reason.startswith("Database legacy")


def test_inactive_rule_does_not_exclude(dataset):
    scope_service.create_rule({
        "name": "Nonaktif",
        "dimension": "environment",
        "match_value": "production",
        "reason": "Tidak dipakai.",
        "active": False,
    }, db_path=dataset.db_path)
    analysis = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    assert analysis.exclusions == []
    assert {s.code for s in analysis.included_servers} == {"SRV-A", "SRV-B"}


def test_scope_rule_requires_reason(db_path):
    with pytest.raises(ValidationError, match="Alasan"):
        scope_service.create_rule({
            "name": "Tanpa alasan",
            "dimension": "server",
            "match_value": "SRV-A",
            "reason": "",
        }, db_path=db_path)


def test_baseline_snapshot_keeps_stats_after_source_batch_deleted(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline awal", dataset.analysis, db_path=dataset.db_path
    )
    batch_service.delete_batch(dataset.cpu_batch, db_path=dataset.db_path)

    baseline = baseline_service.get_baseline(baseline_id, db_path=dataset.db_path)
    assert len(baseline["stats"]) == 4
    assert len(baseline["sources"]) == 2
    cpu_a = next(
        item for item in baseline["stats"]
        if item["server_code"] == "SRV-A" and item["metric"] == "cpu"
    )
    assert cpu_a["avg_value"] == pytest.approx(25)
    assert cpu_a["p95_value"] == pytest.approx(38.5)


def test_baseline_name_is_required(dataset):
    with pytest.raises(ValidationError):
        baseline_service.create_baseline("  ", dataset.analysis, db_path=dataset.db_path)


def test_missing_baseline_raises_not_found(dataset):
    with pytest.raises(NotFoundError):
        baseline_service.get_baseline(999, db_path=dataset.db_path)


def test_compare_flags_scope_exclusion_and_inventory_changes(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline", dataset.analysis, db_path=dataset.db_path
    )
    _update_server(dataset.db_path, "SRV-A", vcpu=8)
    add_server(dataset.db_path, "SRV-C", name="New C", vcpu=2, ram_gib=4)
    _update_server(
        dataset.db_path, "SRV-B",
        scope_status="excluded", exclusion_reason="Keluar scope setelah review.",
    )
    current = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )

    comparison = baseline_service.compare(
        baseline_id, current, db_path=dataset.db_path
    )
    assert comparison["comparable"] is True
    assert "SRV-C" in comparison["scope_added"]
    assert "SRV-B" in comparison["scope_removed"]
    assert "SRV-B" in comparison["exclusion_added"]
    assert any("SRV-A" in item for item in comparison["inventory_changes"])


def test_compare_flags_quality_change_and_keeps_pp_separate(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline", dataset.analysis, db_path=dataset.db_path
    )
    settings_service.update_thresholds(80, 50, 100, "UTC", db_path=dataset.db_path)
    current = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    comparison = baseline_service.compare(
        baseline_id, current, db_path=dataset.db_path
    )
    assert comparison["comparable"] is True
    assert comparison["quality_changes"]
    row = next(
        item for item in comparison["rows"]
        if item["server_code"] == "SRV-A" and item["metric"] == "cpu"
    )
    assert row["quality_changed"] is True
    assert row["delta"]["avg"]["pp"] == pytest.approx(0)
    assert row["delta"]["avg"]["relative_pct"] == pytest.approx(0)


def test_compare_flags_metadata_changes_when_sources_differ(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline", dataset.analysis, db_path=dataset.db_path
    )
    current = analyze(
        START, END, [], [dataset.memory_batch], "UTC", db_path=dataset.db_path
    )
    comparison = baseline_service.compare(
        baseline_id, current, db_path=dataset.db_path
    )
    assert comparison["comparable"] is False
    assert any("jenis statistik" in item for item in comparison["metadata_changes"])
    assert any("interval" in item for item in comparison["metadata_changes"])


def test_compare_reports_percentage_point_and_relative_percent(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline", dataset.analysis, db_path=dataset.db_path
    )
    new_cpu_batch, _ = add_time_batch(
        dataset.db_path, "cpu",
        {"SRV-A": series(START + 4 * 3600, [30, 30, 30, 30])},
    )
    current = analyze(
        START + 4 * 3600, END + 4 * 3600, [new_cpu_batch], [dataset.memory_batch],
        "UTC", db_path=dataset.db_path,
    )
    comparison = baseline_service.compare(
        baseline_id, current, db_path=dataset.db_path
    )
    row = next(
        item for item in comparison["rows"]
        if item["server_code"] == "SRV-A" and item["metric"] == "cpu"
    )
    assert row["before"]["avg"] == pytest.approx(25)
    assert row["after"]["avg"] == pytest.approx(30)
    assert row["delta"]["avg"]["pp"] == pytest.approx(5)
    assert row["delta"]["avg"]["relative_pct"] == pytest.approx(20)
