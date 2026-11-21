import pytest

from cloudsim.errors import AnalysisError, ImportBlocked
from cloudsim.services import inventory_import_service, timeseries_import_service
from cloudsim.services.analysis_service import analyze
from tests.helpers import (
    END,
    HOUR,
    INVENTORY_HEADERS,
    INVENTORY_MAPPING,
    START,
    add_server,
    add_time_batch,
    csv_bytes,
    preview_ts,
    series,
    server_data,
)


def _inventory_preview(db_path, rows):
    data = csv_bytes(INVENTORY_HEADERS, rows)
    return inventory_import_service.preview_inventory(
        data, "inventaris.csv", INVENTORY_MAPPING, db_path=db_path
    )


def test_inventory_duplicate_codes_are_flagged_not_silently_chosen(db_path):
    preview = _inventory_preview(db_path, [
        server_data("SRV-1"),
        server_data("srv-1", name="Duplikat"),
    ])
    codes = {issue["code"] for issue in preview.errors}
    assert "E_DUP_FILE" in codes
    assert preview.accepted_count == 0
    with pytest.raises(ImportBlocked):
        inventory_import_service.save_inventory_import(preview, db_path=db_path)
    with pytest.raises(ImportBlocked):
        inventory_import_service.save_inventory_import(
            preview, allow_partial=True, db_path=db_path
        )


def test_inventory_empty_required_value_is_error_not_zero(db_path):
    preview = _inventory_preview(db_path, [server_data("SRV-1", vcpu="")])
    assert preview.accepted_count == 0
    assert any("vCPU" in issue["detail"] for issue in preview.errors)


def test_inventory_partial_price_is_rejected(db_path):
    preview = _inventory_preview(db_path, [
        server_data("SRV-1", price_amount=100, price_currency=""),
    ])
    assert preview.accepted_count == 0
    assert any("Mata uang" in issue["detail"] for issue in preview.errors)


def test_inventory_does_not_overwrite_existing_server(db_path):
    add_server(db_path, "SRV-1", vcpu=4)
    preview = _inventory_preview(db_path, [server_data("srv-1", vcpu=16)])
    assert preview.accepted_count == 0
    assert any("sudah ada" in issue["detail"] for issue in preview.errors)


def test_inventory_roundtrip_and_file_hash_warning(db_path):
    preview = _inventory_preview(db_path, [
        server_data("SRV-1"),
        server_data("SRV-2", environment="staging"),
    ])
    assert preview.errors == []
    saved = inventory_import_service.save_inventory_import(preview, db_path=db_path)
    assert saved["created"] == 2

    again = _inventory_preview(db_path, [
        server_data("SRV-1"),
        server_data("SRV-2", environment="staging"),
    ])
    assert any(issue["code"] == "W_FILE_HASH" for issue in again.warnings)
    assert again.accepted_count == 0


def test_timeseries_blank_value_is_error_not_zero(db_path):
    add_server(db_path, "SRV-1")
    preview = preview_ts(db_path, "cpu", [["SRV-1", "2026-01-01 00:00:00", ""]])
    assert preview.accepted_count == 0
    assert any("kosong" in issue["detail"] for issue in preview.errors)
    with pytest.raises(ImportBlocked):
        timeseries_import_service.save_timeseries_import(preview, db_path=db_path)


@pytest.mark.parametrize("value", [-1, 100.01, 101])
def test_timeseries_out_of_range_is_rejected(db_path, value):
    add_server(db_path, "SRV-1")
    preview = preview_ts(
        db_path, "cpu", [["SRV-1", "2026-01-01 00:00:00", value]]
    )
    assert preview.accepted_count == 0
    assert any("rentang" in issue["detail"] for issue in preview.errors)


def test_timeseries_identical_duplicates_warn_and_keep_one(db_path):
    add_server(db_path, "SRV-1")
    preview = preview_ts(db_path, "cpu", [
        ["SRV-1", "2026-01-01 00:00:00", 10],
        ["SRV-1", "2026-01-01 00:00:00", 10],
    ])
    assert preview.errors == []
    assert preview.accepted_count == 1
    assert any(issue["code"] == "W_DUP_FILE_IDENTICAL" for issue in preview.warnings)
    saved = timeseries_import_service.save_timeseries_import(preview, db_path=db_path)
    assert saved["created"] == 1


def test_timeseries_conflicting_duplicates_are_all_blocked(db_path):
    add_server(db_path, "SRV-1")
    preview = preview_ts(db_path, "cpu", [
        ["SRV-1", "2026-01-01 00:00:00", 10],
        ["SRV-1", "2026-01-01 00:00:00", 20],
    ])
    assert preview.accepted_count == 0
    assert sum(issue["code"] == "E_DUP_FILE_CONFLICT" for issue in preview.errors) == 2
    with pytest.raises(ImportBlocked):
        timeseries_import_service.save_timeseries_import(preview, db_path=db_path)


def test_conflict_with_existing_database_is_not_overwritten(db_path):
    add_server(db_path, "SRV-1")
    batch_id, _ = add_time_batch(db_path, "cpu", {
        "SRV-1": series(START, [10]),
    }, interval_minutes=60)
    preview = preview_ts(db_path, "cpu", [["SRV-1", "2026-01-01 00:00:00", 20]])
    assert preview.accepted_count == 0
    assert any(issue["code"] == "E_DUP_DB_CONFLICT" for issue in preview.errors)

    analysis = analyze(START, END, [batch_id], [], "UTC", db_path=db_path)
    assert analysis.stats_for("SRV-1", "cpu").avg == pytest.approx(10)


def test_identical_existing_database_rows_are_skipped(db_path):
    add_server(db_path, "SRV-1")
    add_time_batch(db_path, "cpu", {"SRV-1": series(START, [10])})
    preview = preview_ts(db_path, "cpu", [["SRV-1", "2026-01-01 00:00:00", 10]])
    assert preview.accepted_count == 0
    assert any(issue["code"] == "W_DUP_DB_IDENTICAL" for issue in preview.warnings)
    with pytest.raises(ImportBlocked):
        timeseries_import_service.save_timeseries_import(preview, db_path=db_path)


def test_source_timezone_is_converted_to_utc(db_path):
    add_server(db_path, "SRV-1")
    preview = preview_ts(
        db_path, "cpu", [["SRV-1", "2026-01-01 07:00:00", 10]],
        timezone_name="Asia/Jakarta",
    )
    assert preview.errors == []
    assert preview.accepted_rows[0]["ts_utc"] == START


@pytest.mark.parametrize("timestamp", [
    "2026-11-01 01:30:00",
    "2026-03-08 02:30:00",
])
def test_dst_ambiguous_or_nonexistent_local_time_is_rejected(db_path, timestamp):
    add_server(db_path, "SRV-1")
    preview = preview_ts(
        db_path, "cpu", [["SRV-1", timestamp, 10]],
        timezone_name="America/New_York",
    )
    assert preview.accepted_count == 0
    assert any("DST" in issue["detail"] for issue in preview.errors)


def test_microsecond_timestamp_is_rejected(db_path):
    add_server(db_path, "SRV-1")
    preview = preview_ts(
        db_path, "cpu", [["SRV-1", "2026-01-01 00:00:00.500000", 10]]
    )
    assert preview.accepted_count == 0
    assert any("pecahan detik" in issue["detail"] for issue in preview.errors)


def test_unknown_interval_disables_completeness_instead_of_zero(db_path):
    add_server(db_path, "SRV-1")
    batch, _ = add_time_batch(
        db_path, "cpu", {"SRV-1": series(START, [10, 20, 30, 40])},
        interval_minutes=None,
    )
    analysis = analyze(START, END, [batch], [], "UTC", db_path=db_path)
    item = analysis.stats_for("SRV-1", "cpu")
    assert analysis.interval_by_metric["cpu"] is None
    assert item.completeness_pct is None
    assert "completeness_unavailable" in item.flags


def test_gap_reduces_completeness_without_imputing_samples(db_path):
    from cloudsim.services import settings_service

    settings_service.update_thresholds(80, 80, 1, "UTC", db_path=db_path)
    add_server(db_path, "SRV-1")
    batch, _ = add_time_batch(
        db_path, "cpu", {"SRV-1": series(START, [10, 20, 30, 40])}
    )
    analysis = analyze(START, START + 6 * HOUR, [batch], [], "UTC", db_path=db_path)
    item = analysis.stats_for("SRV-1", "cpu")
    assert item.sample_count == 4
    assert item.expected_count == 6
    assert item.completeness_pct == pytest.approx(4 / 6 * 100)
    assert "low_completeness" in item.flags


def test_mixed_source_statistic_types_are_blocked(db_path):
    add_server(db_path, "SRV-1")
    average_batch, _ = add_time_batch(
        db_path, "cpu", {"SRV-1": series(START, [10])}, statistic_type="average"
    )
    maximum_batch, _ = add_time_batch(
        db_path, "cpu",
        {"SRV-1": series(START + 86400, [20])},
        statistic_type="maximum",
    )
    with pytest.raises(AnalysisError, match="jenis statistik"):
        analyze(START, START + 2 * 86400, [average_batch, maximum_batch], [],
                "UTC", db_path=db_path)


def test_mixed_source_intervals_are_blocked(db_path):
    add_server(db_path, "SRV-1")
    hourly, _ = add_time_batch(
        db_path, "cpu", {"SRV-1": series(START, [10])}, interval_minutes=60
    )
    half_hourly, _ = add_time_batch(
        db_path, "cpu",
        {"SRV-1": series(START + 86400, [20])},
        interval_minutes=30,
    )
    with pytest.raises(AnalysisError, match="interval berbeda"):
        analyze(START, START + 2 * 86400, [hourly, half_hourly], [],
                "UTC", db_path=db_path)


def test_cpu_and_memory_may_use_different_source_types(db_path):
    add_server(db_path, "SRV-1")
    cpu_batch, _ = add_time_batch(
        db_path, "cpu", {"SRV-1": series(START, [10, 20])},
        statistic_type="average",
    )
    memory_batch, _ = add_time_batch(
        db_path, "memory", {"SRV-1": series(START, [80, 90])},
        statistic_type="maximum",
    )
    analysis = analyze(START, END, [cpu_batch], [memory_batch], "UTC", db_path=db_path)
    assert analysis.stat_type_by_metric == {"cpu": "average", "memory": "maximum"}


def test_analysis_rejects_wrong_batch_type_and_invalid_window(dataset):
    with pytest.raises(AnalysisError, match="bertipe memory"):
        analyze(START, END, [dataset.memory_batch], [], "UTC", db_path=dataset.db_path)
    with pytest.raises(AnalysisError, match="Akhir periode"):
        analyze(END, START, [dataset.cpu_batch], [], "UTC", db_path=dataset.db_path)
