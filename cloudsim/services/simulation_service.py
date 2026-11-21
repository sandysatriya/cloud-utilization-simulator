from datetime import date as date_cls

from cloudsim.analysis.cost import price_difference
from cloudsim.analysis.models import AnalysisResult
from cloudsim.analysis.resize import classify_estimate, resize_value, sufficiency_reasons
from cloudsim.config import FORMULA_VERSION_RESIZE, PRICE_UNITS
from cloudsim.db.connection import read_connection, transaction
from cloudsim.db.repositories import settings as settings_repo
from cloudsim.db.repositories import simulations as simulation_repo
from cloudsim.errors import NotFoundError, ValidationError
from cloudsim.io.parsers import parse_currency


def _source_price(server) -> dict | None:
    if server.price_amount is None:
        return None
    return {
        "amount": server.price_amount,
        "currency": server.price_currency,
        "unit": server.price_unit,
        "unit_label": server.price_unit_label,
        "source_date": server.price_source_date,
    }


def _target_price(amount, currency, unit, unit_label, source_date) -> dict | None:
    if amount in (None, ""):
        return None
    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Harga target harus berupa angka.")
    if amount_value < 0:
        raise ValidationError("Harga target tidak boleh negatif.")
    currency_value = parse_currency(currency)
    if not currency_value:
        raise ValidationError("Mata uang harga target wajib diisi.")
    if unit not in PRICE_UNITS:
        raise ValidationError("Satuan harga target tidak valid.")
    label = str(unit_label or "").strip() or None
    if unit == "other" and not label:
        raise ValidationError("Satuan 'Lainnya' memerlukan label.")
    if not source_date:
        raise ValidationError("Tanggal sumber harga target wajib diisi.")
    try:
        date_cls.fromisoformat(str(source_date))
    except ValueError:
        raise ValidationError("Tanggal sumber harga target harus berformat YYYY-MM-DD.")
    return {
        "amount": amount_value,
        "currency": currency_value,
        "unit": unit,
        "unit_label": label if unit == "other" else None,
        "source_date": str(source_date),
    }


def compute_resize(
    analysis: AnalysisResult,
    server_code: str,
    target_vcpu,
    target_ram_gib,
    *,
    warning_threshold_pct: float | None = None,
    target_instance_type: str | None = None,
    target_price_amount=None,
    target_price_currency=None,
    target_price_unit=None,
    target_price_unit_label=None,
    target_price_source_date=None,
    db_path=None,
) -> dict:
    if server_code in analysis.excluded_codes:
        raise ValidationError(
            f"Server {server_code} dikecualikan dari scope; simulasi tidak boleh "
            "menghasilkan rekomendasi untuk server yang dikecualikan."
        )
    try:
        target_vcpu_value = int(target_vcpu)
    except (TypeError, ValueError):
        raise ValidationError("vCPU target harus bilangan bulat.")
    if target_vcpu_value <= 0:
        raise ValidationError("vCPU target harus lebih besar dari 0.")
    try:
        target_ram_value = float(target_ram_gib)
    except (TypeError, ValueError):
        raise ValidationError("RAM target harus berupa angka.")
    if target_ram_value <= 0:
        raise ValidationError("RAM target harus lebih besar dari 0.")

    with read_connection(db_path) as conn:
        if warning_threshold_pct is None:
            warning_threshold_pct = settings_repo.get_float(
                conn, "warning_threshold_pct", 80.0
            )
    threshold = float(warning_threshold_pct)
    if not (0 < threshold <= 100):
        raise ValidationError("Ambang peringatan harus di antara 0 dan 100 persen.")

    server_stats = [s for s in analysis.stats if s.server.code == server_code]
    if not server_stats:
        raise NotFoundError(f"Statistik server {server_code} tidak ditemukan dalam analisis.")
    server = server_stats[0].server

    metric_sufficiency: dict[str, dict] = {}
    for metric in ("cpu", "memory"):
        item = analysis.stats_for(server_code, metric)
        if item is None:
            metric_sufficiency[metric] = {"sufficient": False, "reasons": ["not_analyzed"]}
            continue
        reasons = sufficiency_reasons(
            item.sample_count, item.completeness_pct,
            analysis.min_samples, analysis.min_completeness_pct,
        )
        metric_sufficiency[metric] = {"sufficient": not reasons, "reasons": reasons}

    available = [
        analysis.stats_for(server_code, metric) for metric in ("cpu", "memory")
    ]
    available = [item for item in available if item is not None]
    completeness_values = [
        item.completeness_pct for item in available if item.completeness_pct is not None
    ]
    completeness = min(completeness_values) if completeness_values else None
    data_sufficient = all(
        metric_sufficiency[metric]["sufficient"] for metric in ("cpu", "memory")
    )

    results = []
    for metric in ("cpu", "memory"):
        item = analysis.stats_for(server_code, metric)
        source_capacity = server.vcpu if metric == "cpu" else server.ram_gib
        target_capacity = target_vcpu_value if metric == "cpu" else target_ram_value
        reasons = metric_sufficiency[metric]["reasons"]
        for stat_name in ("avg", "p95", "max"):
            before = getattr(item, stat_name) if item else None
            after = resize_value(before, source_capacity, target_capacity)
            if before is None or not item or "metric_unavailable" in item.flags:
                flag = "not_available"
            elif reasons:
                flag = "insufficient_data"
            else:
                flag = classify_estimate(after, threshold)
            results.append({
                "metric": metric,
                "stat_name": stat_name,
                "before": before,
                "after": after,
                "flag": flag,
                "reasons": reasons,
            })

    source_price = _source_price(server)
    target_price = _target_price(
        target_price_amount, target_price_currency, target_price_unit,
        target_price_unit_label, target_price_source_date,
    )
    difference, price_message = price_difference(source_price, target_price)

    assumptions = [
        "Estimasi memakai asumsi beban tetap: nilai utilization lama dikali rasio kapasitas.",
        "Estimasi CPU hanya relevan jika kemampuan per-vCPU sebanding.",
        "Tidak menjamin performa aplikasi, latency, throughput, atau penggunaan memory aktual.",
        "I/O, jaringan, lisensi, dan kebutuhan aplikasi belum dinilai.",
        "Tipe instance target belum tervalidasi; verifikasi sendiri sebelum dipakai.",
        "Hasil simulasi bukan rekomendasi resize otomatis.",
    ]

    return {
        "simulation_id": None,
        "server": server,
        "server_code": server.code,
        "target_vcpu": target_vcpu_value,
        "target_ram_gib": target_ram_value,
        "target_instance_type": (str(target_instance_type).strip() or None)
        if target_instance_type else None,
        "target_instance_type_validated": False,
        "warning_threshold_pct": threshold,
        "results": results,
        "data_sufficient": data_sufficient,
        "completeness_pct": completeness,
        "metric_sufficiency": metric_sufficiency,
        "price": {
            "source": source_price,
            "target": target_price,
            "difference": difference,
            "message": price_message,
        },
        "assumptions": assumptions,
        "formula_version": FORMULA_VERSION_RESIZE,
        "auto_recommendation": False,
    }


def save_resize(
    analysis: AnalysisResult,
    server_code: str,
    target_vcpu,
    target_ram_gib,
    *,
    name: str,
    warning_threshold_pct: float | None = None,
    target_instance_type: str | None = None,
    target_price_amount=None,
    target_price_currency=None,
    target_price_unit=None,
    target_price_unit_label=None,
    target_price_source_date=None,
    notes: str | None = None,
    db_path=None,
) -> dict:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise ValidationError("Nama simulasi wajib diisi.")
    calculation = compute_resize(
        analysis, server_code, target_vcpu, target_ram_gib,
        warning_threshold_pct=warning_threshold_pct,
        target_instance_type=target_instance_type,
        target_price_amount=target_price_amount,
        target_price_currency=target_price_currency,
        target_price_unit=target_price_unit,
        target_price_unit_label=target_price_unit_label,
        target_price_source_date=target_price_source_date,
        db_path=db_path,
    )
    with transaction(db_path) as conn:
        simulation_id = simulation_repo.save_simulation(
            conn,
            name=clean_name,
            server=calculation["server"],
            analysis=analysis,
            target_vcpu=calculation["target_vcpu"],
            target_ram_gib=calculation["target_ram_gib"],
            target_instance_type=calculation["target_instance_type"],
            warning_threshold_pct=calculation["warning_threshold_pct"],
            data_sufficient=calculation["data_sufficient"],
            results=calculation["results"],
            notes=notes,
            target_price=calculation["price"]["target"],
            completeness_pct=calculation["completeness_pct"],
        )
    calculation["simulation_id"] = simulation_id
    return calculation


def list_simulations(db_path=None) -> list[dict]:
    with read_connection(db_path) as conn:
        return simulation_repo.list_simulations(conn)


def get_simulation(simulation_id: int, db_path=None) -> dict:
    with read_connection(db_path) as conn:
        data = simulation_repo.get_simulation(conn, simulation_id)
    if data is None:
        raise NotFoundError("Simulasi tidak ditemukan.")
    return data


def delete_simulation(simulation_id: int, db_path=None) -> None:
    with transaction(db_path) as conn:
        simulation_repo.delete_simulation(conn, simulation_id)
