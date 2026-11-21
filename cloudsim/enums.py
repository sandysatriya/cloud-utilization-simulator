SCOPE_STATUS = {
    "in_scope": "In scope",
    "excluded": "Dikecualikan",
}

STATISTIC_TYPES = {
    "average": "Average (rata-rata per interval)",
    "maximum": "Maximum (nilai maksimum per interval)",
    "other": "Lainnya",
}

PRICE_UNITS = {
    "per_hour": "Per jam",
    "per_month": "Per bulan",
    "per_vcpu_hour": "Per vCPU-jam",
    "per_gib_month": "Per GiB-bulan",
    "other": "Lainnya",
}

SCOPE_DIMENSIONS = {
    "environment": "Environment",
    "workload": "Workload",
    "region": "Region",
    "server": "Kode server",
}

KPI_STATUS = {
    "unconfigured": "Belum Dikonfigurasi",
    "draft": "Draf",
    "approved": "Disetujui",
}

AGGREGATE_METHODS = {
    "none": "Tanpa agregasi (per server)",
    "simple_mean": "Rata-rata sederhana antarserver",
    "capacity_weighted_vcpu": "Berbobot vCPU",
    "capacity_weighted_ram": "Berbobot RAM",
}

KPI_OPERATORS = {
    "lte": "<= target",
    "gte": ">= target",
    "between": "Di antara dua batas",
}

KPI_MEASURES = {
    "avg": "Rata-rata",
    "p95": "P95",
    "max": "Maksimum",
}

ISSUE_SEVERITY = {
    "error": "Error",
    "warning": "Peringatan",
}

QUALITY_FLAGS = {
    "low_samples": "Jumlah sampel di bawah ambang",
    "low_completeness": "Kelengkapan di bawah ambang",
    "completeness_unavailable": "Kelengkapan tidak dapat dihitung",
    "metric_unavailable": "Metrik tidak tersedia",
    "no_samples": "Tidak ada sampel pada periode ini",
    "metadata_mixed": "Metadata batch tidak seragam",
}

ESTIMATE_FLAGS = {
    "normal": "Normal",
    "near_threshold": "Mendekati ambang",
    "over_100": "Melebihi 100%",
    "insufficient_data": "Data belum cukup",
    "not_available": "Tidak tersedia",
}

EXCLUSION_SOURCES = {
    "manual": "Manual",
    "rule": "Aturan scope",
}


def label(mapping: dict, code):
    if code is None:
        return "-"
    return mapping.get(code, str(code))
