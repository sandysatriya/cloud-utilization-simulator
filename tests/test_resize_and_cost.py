import pytest

from cloudsim.analysis.cost import price_difference
from cloudsim.analysis.resize import (
    classify_estimate,
    resize_value,
    sufficiency_reasons,
)
from cloudsim.errors import NotFoundError, ValidationError
from cloudsim.services import simulation_service
from cloudsim.services.analysis_service import analyze
from tests.helpers import END, START, add_server

SOURCE_PRICE = {
    "amount": 100.0,
    "currency": "IDR",
    "unit": "per_month",
    "unit_label": None,
    "source_date": "2026-01-01",
}


def _result(result, metric, stat_name):
    return next(
        item for item in result["results"]
        if item["metric"] == metric and item["stat_name"] == stat_name
    )


def test_resize_formula_same_and_reduced_capacity(dataset):
    same = simulation_service.compute_resize(
        dataset.analysis, "SRV-A", 4, 8, warning_threshold_pct=80,
        db_path=dataset.db_path,
    )
    assert same["data_sufficient"] is True
    assert _result(same, "cpu", "avg")["before"] == pytest.approx(25)
    assert _result(same, "cpu", "avg")["after"] == pytest.approx(25)
    assert _result(same, "cpu", "avg")["flag"] == "normal"
    assert same["auto_recommendation"] is False

    reduced = simulation_service.compute_resize(
        dataset.analysis, "SRV-A", 2, 4, warning_threshold_pct=80,
        db_path=dataset.db_path,
    )
    assert _result(reduced, "cpu", "avg")["after"] == pytest.approx(50)
    assert _result(reduced, "cpu", "p95")["after"] == pytest.approx(77)
    assert _result(reduced, "cpu", "max")["after"] == pytest.approx(80)
    assert _result(reduced, "cpu", "max")["flag"] == "near_threshold"


def test_estimates_above_100_are_flagged_not_clipped(dataset):
    result = simulation_service.compute_resize(
        dataset.analysis, "SRV-A", 1, 2, warning_threshold_pct=80,
        db_path=dataset.db_path,
    )
    cpu_avg = _result(result, "cpu", "avg")
    memory_avg = _result(result, "memory", "avg")
    assert cpu_avg["after"] == pytest.approx(100)
    assert cpu_avg["flag"] == "near_threshold"
    assert memory_avg["after"] == pytest.approx(350)
    assert memory_avg["flag"] == "over_100"
    assert max(
        item["after"] for item in result["results"]
        if item["after"] is not None
    ) > 100


def test_insufficient_data_is_marked_not_recommended(dataset):
    add_server(dataset.db_path, "SRV-C", name="No data", vcpu=2, ram_gib=4)
    analysis = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    result = simulation_service.compute_resize(
        analysis, "SRV-C", 1, 2, db_path=dataset.db_path
    )
    assert result["data_sufficient"] is False
    assert all(item["flag"] in {"insufficient_data", "not_available"}
               for item in result["results"])
    assert "no_samples" in result["metric_sufficiency"]["cpu"]["reasons"]


def test_excluded_server_cannot_be_simulated(dataset):
    from cloudsim.services import scope_service

    scope_service.create_rule({
        "name": "Exclude B",
        "dimension": "server",
        "match_value": "SRV-B",
        "reason": "Keluar scope.",
    }, db_path=dataset.db_path)
    analysis = analyze(
        START, END, [dataset.cpu_batch], [dataset.memory_batch], "UTC",
        db_path=dataset.db_path,
    )
    with pytest.raises(ValidationError, match="dikecualikan"):
        simulation_service.compute_resize(
            analysis, "SRV-B", 4, 8, db_path=dataset.db_path
        )


@pytest.mark.parametrize("vcpu,ram", [(0, 8), (2, 0), (-1, 4), (2, -1)])
def test_target_capacity_must_be_positive(dataset, vcpu, ram):
    with pytest.raises(ValidationError, match="target"):
        simulation_service.compute_resize(
            dataset.analysis, "SRV-A", vcpu, ram, db_path=dataset.db_path
        )


def test_warning_threshold_must_be_in_range(dataset):
    for threshold in (0, 101):
        with pytest.raises(ValidationError, match="Ambang"):
            simulation_service.compute_resize(
                dataset.analysis, "SRV-A", 4, 8,
                warning_threshold_pct=threshold, db_path=dataset.db_path,
            )


def test_price_difference_requires_matching_currency_and_unit():
    source = dict(SOURCE_PRICE)
    target = {**SOURCE_PRICE, "amount": 80.0}
    difference, message = price_difference(source, target)
    assert difference == pytest.approx(-20)
    assert "bukan estimasi penghematan bulanan" in message

    difference, message = price_difference(source, {**target, "currency": "USD"})
    assert difference is None
    assert "Mata uang" in message

    difference, message = price_difference(source, {**target, "unit": "per_hour"})
    assert difference is None
    assert "Satuan" in message

    difference, message = price_difference(None, target)
    assert difference is None
    assert "sumber" in message

    difference, message = price_difference(source, None)
    assert difference is None
    assert "target" in message


def test_other_price_unit_requires_same_label():
    source = {**SOURCE_PRICE, "unit": "other", "unit_label": "per core"}
    target = {**source, "amount": 90.0, "unit_label": "per core"}
    difference, _ = price_difference(source, target)
    assert difference == pytest.approx(-10)

    difference, message = price_difference(source, {**target, "unit_label": "per socket"})
    assert difference is None
    assert "Label" in message


def test_resize_helpers_classify_boundaries():
    assert resize_value(None, 4, 2) is None
    assert resize_value(40, 4, 2) == pytest.approx(80)
    with pytest.raises(ValidationError):
        resize_value(40, 4, 0)

    assert classify_estimate(None, 80) == "not_available"
    assert classify_estimate(79.9, 80) == "normal"
    assert classify_estimate(80, 80) == "near_threshold"
    assert classify_estimate(100, 80) == "near_threshold"
    assert classify_estimate(100.1, 80) == "over_100"

    assert sufficiency_reasons(0, None, 24, 80) == [
        "no_samples", "low_samples", "completeness_unavailable",
    ]


def test_simulation_target_price_validation_and_snapshot(dataset):
    with pytest.raises(ValidationError, match="Mata uang"):
        simulation_service.compute_resize(
            dataset.analysis, "SRV-A", 4, 8,
            target_price_amount=10, target_price_currency="",
            target_price_unit="per_month", target_price_source_date="2026-01-01",
            db_path=dataset.db_path,
        )
    with pytest.raises(ValidationError, match="Tanggal"):
        simulation_service.compute_resize(
            dataset.analysis, "SRV-A", 4, 8,
            target_price_amount=10, target_price_currency="IDR",
            target_price_unit="per_month", target_price_source_date=None,
            db_path=dataset.db_path,
        )

    saved = simulation_service.save_resize(
        dataset.analysis, "SRV-A", 2, 4,
        name="Simulasi A kecil",
        warning_threshold_pct=80,
        target_instance_type="candidate.small",
        target_price_amount=90,
        target_price_currency="IDR",
        target_price_unit="per_month",
        target_price_source_date="2026-01-05",
        notes="Data fiktif",
        db_path=dataset.db_path,
    )
    assert saved["simulation_id"] == 1
    assert saved["target_instance_type_validated"] is False

    stored = simulation_service.get_simulation(1, db_path=dataset.db_path)
    assert stored["name"] == "Simulasi A kecil"
    assert stored["source_vcpu"] == 4
    assert stored["target_vcpu"] == 2
    assert stored["source_ram_gib"] == 8
    assert stored["target_ram_gib"] == 4
    assert stored["target_price_amount"] == pytest.approx(90)
    assert stored["target_price_currency"] == "IDR"
    assert len(stored["results"]) == 6

    simulation_service.delete_simulation(1, db_path=dataset.db_path)
    with pytest.raises(NotFoundError):
        simulation_service.get_simulation(1, db_path=dataset.db_path)


def test_simulation_name_is_required(dataset):
    with pytest.raises(ValidationError, match="Nama simulasi"):
        simulation_service.save_resize(
            dataset.analysis, "SRV-A", 4, 8, name=" ",
            db_path=dataset.db_path,
        )
