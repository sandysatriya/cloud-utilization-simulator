import pytest

from cloudsim.config import FORMULA_VERSION_KPI
from cloudsim.errors import ValidationError
from cloudsim.services import baseline_service, kpi_service
from cloudsim.services.analysis_service import analyze
from tests.helpers import END, START, add_time_batch, series


def _definition(**overrides):
    data = {
        "name": "CPU P95",
        "description": "KPI contoh untuk pengujian.",
        "metric": "cpu",
        "measure": "p95",
        "aggregate_method": "capacity_weighted_vcpu",
        "operator": "lte",
        "target_value": 50.0,
        "target_value_upper": None,
        "scope_mode": "current_scope",
        "baseline_id": None,
    }
    data.update(overrides)
    return data


def test_unapproved_kpi_is_not_evaluated(dataset):
    kpi_id = kpi_service.save_definition(_definition(), db_path=dataset.db_path)
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "draft"
    result = kpi_service.evaluate_definition(definition, dataset.analysis)
    assert result["available"] is False
    assert result["reason"] == "KPI belum disetujui."


def test_approved_kpi_weighted_evaluation(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(), approve=True, db_path=dataset.db_path
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "approved"
    assert definition["formula_version"] == FORMULA_VERSION_KPI

    result = kpi_service.evaluate_definition(definition, dataset.analysis)
    assert result["available"] is True
    assert result["aggregate_value"] == pytest.approx(
        (38.5 * 4 + 48.5 * 8) / 12
    )
    assert result["evaluated"] is True
    assert result["total_count"] == 2


def test_simple_mean_and_per_server_modes(dataset):
    simple_id = kpi_service.save_definition(
        _definition(aggregate_method="simple_mean", target_value=45),
        approve=True, db_path=dataset.db_path,
    )
    simple = kpi_service.evaluate_definition(
        kpi_service.get_definition(simple_id, db_path=dataset.db_path),
        dataset.analysis,
    )
    assert simple["aggregate_value"] == pytest.approx(43.5)
    assert simple["evaluated"] is True
    assert "bukan utilization seluruh kapasitas" in simple["aggregate_disclaimer"]

    per_server_id = kpi_service.save_definition(
        _definition(aggregate_method="none", target_value=50),
        approve=True, db_path=dataset.db_path,
    )
    per_server = kpi_service.evaluate_definition(
        kpi_service.get_definition(per_server_id, db_path=dataset.db_path),
        dataset.analysis,
    )
    assert per_server["aggregate_value"] is None
    assert per_server["passed_count"] == 2
    assert per_server["total_count"] == 2


def test_between_operator_uses_user_bounds(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(operator="between", target_value=44, target_value_upper=46),
        approve=True, db_path=dataset.db_path,
    )
    result = kpi_service.evaluate_definition(
        kpi_service.get_definition(kpi_id, db_path=dataset.db_path),
        dataset.analysis,
    )
    assert result["evaluated"] is True


def test_baseline_scope_uses_baseline_snapshot(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline KPI", dataset.analysis, db_path=dataset.db_path
    )
    kpi_id = kpi_service.save_definition(
        _definition(scope_mode="baseline_scope", baseline_id=baseline_id),
        approve=True, db_path=dataset.db_path,
    )
    new_cpu_batch, _ = add_time_batch(
        dataset.db_path, "cpu",
        {"SRV-A": series(START + 4 * 3600, [90, 90]), "SRV-B": series(START + 4 * 3600, [90, 90])},
    )
    current = analyze(
        START + 4 * 3600, END + 4 * 3600, [new_cpu_batch], [dataset.memory_batch],
        "UTC", db_path=dataset.db_path,
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)

    current_scope = kpi_service.evaluate_definition(definition, current)
    baseline_scope = kpi_service.evaluate_definition(
        definition, current,
        baseline_service.get_baseline(baseline_id, db_path=dataset.db_path),
    )
    assert current_scope["available"] is False
    assert "Baseline" in current_scope["reason"]
    assert baseline_scope["scope_mode"] == "baseline_scope"
    assert baseline_scope["aggregate_value"] == pytest.approx(
        (38.5 * 4 + 48.5 * 8) / 12
    )


def test_approval_requires_complete_definition(dataset):
    with pytest.raises(ValidationError, match="metrik"):
        kpi_service.save_definition(
            _definition(metric=None), approve=True, db_path=dataset.db_path
        )
    with pytest.raises(ValidationError, match="Measure"):
        kpi_service.save_definition(
            _definition(measure="sum"), approve=True, db_path=dataset.db_path
        )
    with pytest.raises(ValidationError, match="Target"):
        kpi_service.save_definition(
            _definition(target_value=None), approve=True, db_path=dataset.db_path
        )
    with pytest.raises(ValidationError, match="batas atas"):
        kpi_service.save_definition(
            _definition(operator="between", target_value_upper=None),
            approve=True, db_path=dataset.db_path,
        )


def test_baseline_scope_requires_baseline(dataset):
    with pytest.raises(ValidationError, match="baseline"):
        kpi_service.save_definition(
            _definition(scope_mode="baseline_scope", baseline_id=None),
            db_path=dataset.db_path,
        )


def test_thresholds_must_not_overlap(dataset):
    with pytest.raises(ValidationError, match="tumpang tindih"):
        kpi_service.save_definition(
            _definition(),
            thresholds=[
                {"label": "Rendah", "min_value": 0, "max_value": 80},
                {"label": "Sedang", "min_value": 50, "max_value": 100},
            ],
            approve=True,
            db_path=dataset.db_path,
        )


def test_adjacent_thresholds_are_allowed(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(),
        thresholds=[
            {"label": "Rendah", "min_value": None, "max_value": 80, "meaning": "Aman"},
            {"label": "Tinggi", "min_value": 80, "max_value": None, "meaning": "Perhatian"},
        ],
        approve=True,
        db_path=dataset.db_path,
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert [item["label"] for item in definition["thresholds"]] == ["Rendah", "Tinggi"]


def test_revoke_disables_evaluation(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(), approve=True, db_path=dataset.db_path
    )
    kpi_service.revoke_definition(kpi_id, db_path=dataset.db_path)
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "draft"
    assert definition["approved_at"] is None
    assert definition["formula_version"] is None
    result = kpi_service.evaluate_definition(definition, dataset.analysis)
    assert result["available"] is False


def test_saving_existing_kpi_without_approval_returns_to_draft(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(), approve=True, db_path=dataset.db_path
    )
    kpi_service.save_definition(
        _definition(name="Diubah"), kpi_id=kpi_id, db_path=dataset.db_path
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "draft"
    assert definition["name"] == "Diubah"
