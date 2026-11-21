from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from cloudsim.analysis.stats import stat_phrase
from cloudsim.clock import utc_now_iso
from cloudsim.config import (
    APP_NAME,
    APP_VERSION,
    P95_METHOD_LABEL,
    STAT_DISCLAIMER,
)
from cloudsim.enums import (
    ESTIMATE_FLAGS,
    EXCLUSION_SOURCES,
    KPI_STATUS,
    QUALITY_FLAGS,
    label,
)
from cloudsim.io.excel_writer import workbook_bytes

MEASURE_LABELS = {"avg": "Rata-rata", "p95": "P95", "max": "Maksimum"}
METRIC_LABELS = {"cpu": "CPU", "memory": "Memory"}


def _local(ts, tz_name: str) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), ZoneInfo(tz_name)).isoformat(sep=" ")


def _summary_sheet(analysis, simulation, comparison) -> pd.DataFrame:
    rows = [
        ("Aplikasi", APP_NAME),
        ("Versi aplikasi", APP_VERSION),
        ("Waktu export", utc_now_iso()),
        ("Awal periode", _local(analysis.window_start_utc, analysis.display_timezone)),
        ("Akhir periode (eksklusif)", _local(analysis.window_end_utc, analysis.display_timezone)),
        ("Zona waktu tampilan", analysis.display_timezone),
        ("Versi formula statistik", analysis.formula_version),
        ("Metode P95", P95_METHOD_LABEL),
        ("Jumlah server inventaris", len(analysis.servers)),
        ("Server dalam scope", len(analysis.included_servers)),
        ("Server dikecualikan", len(analysis.exclusions)),
        ("Batch CPU", ", ".join(f"#{b.id} {b.file_name}" for b in analysis.cpu_batches) or "(tidak ada)"),
        ("Batch memory", ", ".join(f"#{b.id} {b.file_name}" for b in analysis.memory_batches) or "(tidak ada)"),
        ("Jenis statistik CPU", analysis.stat_type_by_metric.get("cpu") or "(tidak tersedia)"),
        ("Jenis statistik memory", analysis.stat_type_by_metric.get("memory") or "(tidak tersedia)"),
        ("Interval CPU (detik)", analysis.interval_by_metric.get("cpu")),
        ("Interval memory (detik)", analysis.interval_by_metric.get("memory")),
        ("Ambang sampel minimum", analysis.min_samples),
        ("Ambang kelengkapan minimum (%)", analysis.min_completeness_pct),
        ("Baseline dibandingkan", comparison.get("baseline_name") if comparison else "(tidak ada)"),
        ("Simulasi diekspor", simulation.get("name") if simulation else "(tidak ada)"),
        ("Catatan", STAT_DISCLAIMER),
        ("Catatan tambahan", "Data sampel mentah tidak diekspor; hanya ringkasan dan metadata."),
    ]
    return pd.DataFrame(rows, columns=["Keterangan", "Nilai"])


def _stats_sheet(analysis) -> pd.DataFrame:
    rows = []
    for item in analysis.stats:
        batches = analysis.batches_for(item.metric)
        stat_type = analysis.stat_type_by_metric.get(item.metric)
        interval = analysis.interval_by_metric.get(item.metric)
        custom_label = batches[0].statistic_label if batches and batches[0].statistic_label else None
        rows.append({
            "Kode server": item.server.code,
            "Nama": item.server.name,
            "Environment": item.server.environment,
            "Workload": item.server.workload,
            "vCPU": item.server.vcpu,
            "RAM GiB": item.server.ram_gib,
            "Metrik": METRIC_LABELS[item.metric],
            "Jumlah sampel": item.sample_count,
            "Perkiraan sampel": item.expected_count,
            "Kelengkapan (%)": round(item.completeness_pct, 2) if item.completeness_pct is not None else None,
            "Rata-rata (%)": round(item.avg, 4) if item.avg is not None else None,
            "P95 (%)": round(item.p95, 4) if item.p95 is not None else None,
            "Maksimum (%)": round(item.max, 4) if item.max is not None else None,
            "Label rata-rata": stat_phrase("avg", stat_type, interval, custom_label),
            "Label P95": stat_phrase("p95", stat_type, interval, custom_label),
            "Label maksimum": stat_phrase("max", stat_type, interval, custom_label),
            "Flag kualitas": ", ".join(
                QUALITY_FLAGS.get(f, f) for f in item.flags
            ) or "Tidak ada",
        })
    return pd.DataFrame(rows)


def _exclusion_sheet(analysis) -> pd.DataFrame:
    rows = [{
        "Kode server": item.server_code,
        "Nama": item.server_name,
        "Sumber": label(EXCLUSION_SOURCES, item.source),
        "Nama aturan": item.rule_name,
        "Alasan": item.reason,
    } for item in analysis.exclusions]
    return pd.DataFrame(rows, columns=["Kode server", "Nama", "Sumber", "Nama aturan", "Alasan"])


def _source_sheet(analysis) -> pd.DataFrame:
    rows = []
    for batch in [*analysis.cpu_batches, *analysis.memory_batches]:
        rows.append({
            "ID batch": batch.id,
            "Metrik": METRIC_LABELS.get(batch.data_type, batch.data_type),
            "Nama file": batch.file_name,
            "SHA-256": batch.file_sha256,
            "Zona waktu sumber": batch.timezone,
            "Interval (detik)": batch.interval_seconds,
            "Jenis statistik": batch.statistic_type,
            "Label statistik": batch.statistic_label,
            "Awal data (UTC)": _local(batch.period_start_utc, "UTC"),
            "Akhir data (UTC)": _local(batch.period_end_utc, "UTC"),
            "Total baris": batch.total_rows,
            "Diterima": batch.accepted_rows,
            "Ditolak": batch.rejected_rows,
            "Waktu import": batch.imported_at,
            "Catatan": batch.notes,
        })
    return pd.DataFrame(rows)


def _baseline_summary(comparison: dict) -> pd.DataFrame:
    if not comparison:
        return pd.DataFrame(
            [("Baseline", "Tidak ada baseline yang dibandingkan.")],
            columns=["Keterangan", "Nilai"],
        )
    rows = [
        ("Nama baseline", comparison["baseline_name"]),
        ("Dibuat", comparison["baseline_created_at"]),
        ("Versi formula baseline", comparison["baseline_formula_version"]),
        ("Versi formula saat ini", comparison["current_formula_version"]),
        ("Dapat dibandingkan (metadata sama)", "Ya" if comparison["comparable"] else "Tidak"),
        ("Server masuk scope", ", ".join(comparison["scope_added"]) or "-"),
        ("Server keluar scope", ", ".join(comparison["scope_removed"]) or "-"),
        ("Pengecualian baru", ", ".join(comparison["exclusion_added"]) or "-"),
        ("Pengecualian dihapus", ", ".join(comparison["exclusion_removed"]) or "-"),
        ("Alasan pengecualian berubah", ", ".join(comparison["exclusion_changed"]) or "-"),
        ("Perubahan metadata", "; ".join(comparison["metadata_changes"]) or "-"),
        ("Perubahan inventaris", "; ".join(comparison["inventory_changes"]) or "-"),
        ("Perubahan kualitas data", "; ".join(comparison["quality_changes"]) or "-"),
        ("Catatan", "Delta percentage point dan persen relatif dihitung terpisah; "
                   "persen relatif tidak dihitung bila nilai baseline 0."),
    ]
    return pd.DataFrame(rows, columns=["Keterangan", "Nilai"])


def _baseline_delta(comparison: dict) -> pd.DataFrame:
    rows = []
    if not comparison:
        return pd.DataFrame(rows)
    for item in comparison["rows"]:
        row = {
            "Kode server": item["server_code"],
            "Metrik": METRIC_LABELS.get(item["metric"], item["metric"]),
            "Ada di baseline": "Ya" if item["in_baseline"] else "Tidak",
            "Ada di periode ini": "Ya" if item["in_current"] else "Tidak",
        }
        for stat in ("avg", "p95", "max"):
            name = MEASURE_LABELS[stat]
            row[f"{name} baseline (%)"] = item["before"][stat]
            row[f"{name} periode ini (%)"] = item["after"][stat]
            row[f"Delta {name} (pp)"] = item["delta"][stat]["pp"]
            row[f"Delta {name} (%)"] = item["delta"][stat]["relative_pct"]
        row["Sampel baseline"] = item["before_samples"]
        row["Sampel periode ini"] = item["after_samples"]
        row["Kelengkapan baseline (%)"] = item["before_completeness"]
        row["Kelengkapan periode ini (%)"] = item["after_completeness"]
        row["Flag baseline"] = ", ".join(item["before_flags"])
        row["Flag periode ini"] = ", ".join(item["after_flags"])
        row["Kualitas berubah"] = "Ya" if item["quality_changed"] else "Tidak"
        rows.append(row)
    return pd.DataFrame(rows)


def _simulation_summary(simulation: dict | None) -> pd.DataFrame:
    if not simulation:
        return pd.DataFrame(
            [("Simulasi", "Tidak ada simulasi yang diekspor.")],
            columns=["Keterangan", "Nilai"],
        )
    rows = [
        ("Nama", simulation.get("name") or "(tanpa nama)"),
        ("ID simulasi", simulation.get("simulation_id") or simulation.get("id")),
        ("Server", simulation.get("server_code")),
        ("vCPU sumber", simulation.get("source_vcpu") or getattr(simulation.get("server"), "vcpu", None)),
        ("RAM sumber (GiB)", simulation.get("source_ram_gib") or getattr(simulation.get("server"), "ram_gib", None)),
        ("vCPU target", simulation.get("target_vcpu")),
        ("RAM target (GiB)", simulation.get("target_ram_gib")),
        ("Tipe instance target", simulation.get("target_instance_type") or "(tidak diisi)"),
        ("Validasi tipe instance", "Belum tervalidasi"),
        ("Ambang peringatan (%)", simulation.get("warning_threshold_pct")),
        ("Data cukup", "Ya" if simulation.get("data_sufficient") else "Tidak"),
        ("Kelengkapan data minimum (%)", simulation.get("completeness_pct")),
        ("Catatan", "Estimasi dengan asumsi beban tetap; bukan rekomendasi resize otomatis."),
    ]
    if simulation.get("price"):
        price = simulation["price"]
        rows.extend([
            ("Selisih harga", price.get("difference")),
            ("Keterangan harga", price.get("message")),
        ])
    else:
        if simulation.get("target_price_amount") is not None:
            rows.append((
                "Harga target tersimpan",
                f"{simulation['target_price_amount']} {simulation.get('target_price_currency')} "
                f"({simulation.get('target_price_unit')}), "
                f"tanggal {simulation.get('target_price_source_date')}",
            ))
        rows.append((
            "Keterangan harga",
            "Snapshot simulasi tersimpan tidak memuat harga sumber; "
            "selisih harga tidak ditampilkan.",
        ))
    return pd.DataFrame(rows, columns=["Keterangan", "Nilai"])


def _simulation_results(simulation: dict | None) -> pd.DataFrame:
    rows = []
    if not simulation:
        return pd.DataFrame(rows)
    for item in simulation.get("results", []):
        before = item.get("before", item.get("before_value"))
        after = item.get("after", item.get("after_value"))
        reasons = item.get("reasons")
        if reasons is None:
            reasons = ""
        elif isinstance(reasons, list):
            reasons = ", ".join(reasons)
        rows.append({
            "Metrik": METRIC_LABELS.get(item["metric"], item["metric"]),
            "Statistik": MEASURE_LABELS.get(item["stat_name"], item["stat_name"]),
            "Sebelum (%)": before,
            "Sesudah estimasi (%)": after,
            "Flag": label(ESTIMATE_FLAGS, item["flag"]),
            "Alasan data": reasons,
        })
    return pd.DataFrame(rows)


def _kpi_sheet(kpi_results: list[dict] | None) -> pd.DataFrame:
    rows = []
    for entry in kpi_results or []:
        definition = entry.get("definition") or {}
        evaluation = entry.get("evaluation") or {}
        rows.append({
            "ID": definition.get("id"),
            "Nama": definition.get("name"),
            "Status": label(KPI_STATUS, definition.get("status") or "unconfigured"),
            "Metrik": METRIC_LABELS.get(definition.get("metric"), definition.get("metric")),
            "Measure": MEASURE_LABELS.get(definition.get("measure"), definition.get("measure")),
            "Agregasi": definition.get("aggregate_method"),
            "Operator": definition.get("operator"),
            "Target": definition.get("target_value"),
            "Batas atas": definition.get("target_value_upper"),
            "Scope": definition.get("scope_mode"),
            "Baseline ID": definition.get("baseline_id"),
            "Nilai agregat": evaluation.get("aggregate_value"),
            "Jumlah dievaluasi": evaluation.get("total_count"),
            "Jumlah lulus": evaluation.get("passed_count"),
            "Lulus": (
                "Ya" if evaluation.get("evaluated") is True
                else "Tidak" if evaluation.get("evaluated") is False
                else "Tidak tersedia"
            ),
            "Alasan": evaluation.get("reason") or evaluation.get("aggregate_disclaimer"),
            "Versi formula": evaluation.get("formula_version"),
        })
    if not rows:
        rows.append({
            "Nama": "Belum Dikonfigurasi",
            "Status": KPI_STATUS["unconfigured"],
            "Alasan": "Belum ada definisi KPI yang disetujui.",
        })
    return pd.DataFrame(rows)


def _kpi_server_sheet(kpi_results: list[dict] | None) -> pd.DataFrame:
    rows = []
    for entry in kpi_results or []:
        definition = entry.get("definition") or {}
        evaluation = entry.get("evaluation") or {}
        for item in evaluation.get("per_server") or []:
            rows.append({
                "KPI": definition.get("name"),
                "Kode server": item["server_code"],
                "Nilai": item.get("value"),
                "Lulus": (
                    "Ya" if item.get("passed") is True
                    else "Tidak" if item.get("passed") is False
                    else "Tidak dievaluasi"
                ),
            })
    return pd.DataFrame(rows)


def _assumptions_sheet(analysis, simulation, comparison) -> pd.DataFrame:
    rows = [
        ("Batasan umum", STAT_DISCLAIMER),
        ("Metode rata-rata", "Rata-rata aritmetika nilai sampel pada periode."),
        ("Metode P95", P95_METHOD_LABEL + "."),
        ("Kelengkapan", "Hanya dihitung bila interval pengamatan diketahui; "
                        "nilai kosong tidak dianggap nol."),
        ("Agregasi antarserver", "Rata-rata sederhana bukan utilization seluruh kapasitas. "
                                 "Agregasi berbobot harus menyebut bobotnya."),
        ("Sumber statistik", "Jika sumber berupa rata-rata per interval, P95 diberi label "
                             "sebagai P95 rata-rata per interval, bukan puncak sesaat."),
        ("Resize", "Estimasi memakai asumsi beban tetap dan tidak menjamin performa, latency, "
                   "throughput, atau memory aktual. I/O, jaringan, lisensi, dan kebutuhan "
                   "aplikasi belum dinilai."),
        ("Biaya", "Estimasi biaya hanya membandingkan harga input dengan mata uang dan satuan "
                  "yang sama; tidak ada konversi atau asumsi harga proporsional."),
        ("KPI", "KPI tetap Belum Dikonfigurasi sampai formula disetujui pengguna."),
    ]
    for warning in analysis.warnings:
        rows.append(("Peringatan analisis", warning))
    if comparison:
        for item in comparison["metadata_changes"]:
            rows.append(("Peringatan perbandingan", item))
        for item in comparison["quality_changes"]:
            rows.append(("Perubahan kualitas data", item))
        if not comparison["comparable"]:
            rows.append(("Peringatan perbandingan", "Metadata sumber berbeda; "
                                                    "perbandingan tidak sepenuhnya setara."))
    if simulation:
        for item in simulation.get("assumptions", []):
            rows.append(("Asumsi simulasi", item))
    return pd.DataFrame(rows, columns=["Jenis", "Keterangan"])


def build_export(
    analysis,
    *,
    simulation: dict | None = None,
    comparison: dict | None = None,
    kpi_results: list[dict] | None = None,
) -> bytes:
    sheets = [
        ("Ringkasan", _summary_sheet(analysis, simulation, comparison)),
        ("Statistik Server", _stats_sheet(analysis)),
        ("Inventaris Dikecualikan", _exclusion_sheet(analysis)),
        ("Sumber Data", _source_sheet(analysis)),
        ("Baseline Ringkasan", _baseline_summary(comparison)),
        ("Baseline Delta", _baseline_delta(comparison)),
        ("Simulasi Ringkasan", _simulation_summary(simulation)),
        ("Simulasi Hasil", _simulation_results(simulation)),
        ("KPI", _kpi_sheet(kpi_results)),
        ("KPI per Server", _kpi_server_sheet(kpi_results)),
        ("Asumsi & Peringatan", _assumptions_sheet(analysis, simulation, comparison)),
    ]
    return workbook_bytes(sheets)
