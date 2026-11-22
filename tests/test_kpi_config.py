import pytest

from cloudsim.analysis import kpi as kpi_analysis
from cloudsim.config import FORMULA_VERSION_KPI
from cloudsim.errors import ValidationError
from cloudsim.services import baseline_service, kpi_service


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


def test_new_kpi_is_saved_as_draft(dataset):
    kpi_id = kpi_service.save_definition(_definition(), db_path=dataset.db_path)
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "draft"
    assert definition["approved_at"] is None
    assert definition["formula_version"] is None


def test_approved_kpi_stores_configuration(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(operator="between", target_value=44, target_value_upper=46),
        approve=True, db_path=dataset.db_path,
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "approved"
    assert definition["approved_at"] is not None
    assert definition["formula_version"] == FORMULA_VERSION_KPI
    assert definition["metric"] == "cpu"
    assert definition["measure"] == "p95"
    assert definition["aggregate_method"] == "capacity_weighted_vcpu"
    assert definition["target_value"] == 44
    assert definition["target_value_upper"] == 46


def test_baseline_scope_stores_baseline_reference(dataset):
    baseline_id = baseline_service.create_baseline(
        "Baseline KPI", dataset.analysis, db_path=dataset.db_path
    )
    kpi_id = kpi_service.save_definition(
        _definition(scope_mode="baseline_scope", baseline_id=baseline_id),
        approve=True, db_path=dataset.db_path,
    )
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["scope_mode"] == "baseline_scope"
    assert definition["baseline_id"] == baseline_id


def test_kpi_module_has_no_computation():
    for module in (kpi_service, kpi_analysis):
        assert not any(
            name in dir(module)
            for name in ("compute_kpi", "evaluate", "evaluate_definition", "aggregate_value")
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


def test_revoke_returns_kpi_to_draft(dataset):
    kpi_id = kpi_service.save_definition(
        _definition(), approve=True, db_path=dataset.db_path
    )
    kpi_service.revoke_definition(kpi_id, db_path=dataset.db_path)
    definition = kpi_service.get_definition(kpi_id, db_path=dataset.db_path)
    assert definition["status"] == "draft"
    assert definition["approved_at"] is None
    assert definition["formula_version"] is None


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
