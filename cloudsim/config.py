import os
from pathlib import Path

APP_NAME = "Cloud Utilization & Rightsizing Simulator"
APP_VERSION = "0.1.0"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = Path(os.environ.get("CLOUDSIM_DB_PATH", DATA_DIR / "app.db"))

FORMULA_VERSION_STATS = "stats-v1"
FORMULA_VERSION_COMPARE = "compare-v1"
FORMULA_VERSION_RESIZE = "resize-v1"
FORMULA_VERSION_KPI = "kpi-config-v1"

DEFAULT_DISPLAY_TZ = "Asia/Jakarta"
DEFAULT_WARNING_THRESHOLD = 80.0
DEFAULT_MIN_COMPLETENESS = 80.0
DEFAULT_MIN_SAMPLES = 24

SETTING_DEFAULTS = {
    "display_timezone": DEFAULT_DISPLAY_TZ,
    "warning_threshold_pct": str(DEFAULT_WARNING_THRESHOLD),
    "min_completeness_pct": str(DEFAULT_MIN_COMPLETENESS),
    "min_samples": str(DEFAULT_MIN_SAMPLES),
}

P95_METHOD = "linear_interpolation"
P95_METHOD_LABEL = (
    "P95 interpolasi linear (posisi (n-1) x 0,95, sama dengan pandas/Excel PERCENTILE.INC)"
)

PRICE_UNITS = {
    "per_hour": "Per jam",
    "per_month": "Per bulan",
    "per_vcpu_hour": "Per vCPU-jam",
    "per_gib_month": "Per GiB-bulan",
    "other": "Lainnya",
}

STAT_DISCLAIMER = (
    "Aplikasi lokal. Data berasal dari file yang diimpor pengguna. Tidak ada koneksi "
    "ke cloud/produksi, tidak ada perubahan infrastruktur, dan tidak ada rekomendasi "
    "resize otomatis. Hasil simulasi adalah estimasi, bukan jaminan performa."
)


def env_db_path() -> Path:
    return Path(os.environ.get("CLOUDSIM_DB_PATH", DEFAULT_DB_PATH))
