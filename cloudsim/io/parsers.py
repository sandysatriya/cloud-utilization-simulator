import math
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from cloudsim.enums import PRICE_UNITS, SCOPE_STATUS, STATISTIC_TYPES
from cloudsim.errors import ValidationError

DATE_FORMATS = {
    "iso": None,
    "dmy_slash": "%d/%m/%Y",
    "mdy_slash": "%m/%d/%Y",
    "dmy_dash": "%d-%m-%Y",
}


def is_blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def clean_text(value) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_number(value, decimal: str = "dot") -> float:
    if is_blank(value) or isinstance(value, bool):
        raise ValidationError("Nilai kosong/bukan angka.")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(" ", "")
        if decimal == "comma":
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
        try:
            number = float(text)
        except ValueError:
            raise ValidationError(f"Nilai '{value}' bukan angka yang valid.")
    if not math.isfinite(number):
        raise ValidationError("Nilai angka tidak valid.")
    return number


def parse_date_value(value, fmt: str = "iso") -> date:
    if is_blank(value):
        raise ValidationError("Tanggal kosong.")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()
    text = str(value).strip()
    try:
        if fmt == "iso" or DATE_FORMATS.get(fmt) is None:
            return date.fromisoformat(text[:10])
        return datetime.strptime(text, DATE_FORMATS[fmt]).date()
    except ValueError:
        raise ValidationError(f"Tanggal '{value}' tidak sesuai format yang dipilih.")


def validate_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(str(tz_name).strip())
    except Exception:
        raise ValidationError(f"Zona waktu '{tz_name}' tidak dikenal.")


def _attach_local_timezone(dt: datetime, tz: ZoneInfo) -> datetime:
    first = dt.replace(tzinfo=tz, fold=0)
    second = dt.replace(tzinfo=tz, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValidationError(
            f"Waktu lokal {dt.isoformat()} ambigu karena transisi DST; gunakan timestamp ber-offset."
        )
    back = first.astimezone(timezone.utc).astimezone(tz)
    if back.replace(tzinfo=None) != dt:
        raise ValidationError(
            f"Waktu lokal {dt.isoformat()} tidak ada karena transisi DST."
        )
    return first


def parse_datetime_utc(value, fmt: str, tz_name: str) -> int:
    tz = validate_timezone(tz_name)
    if is_blank(value):
        raise ValidationError("Timestamp kosong.")
    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        try:
            if fmt == "iso":
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                pattern = DATE_FORMATS.get(fmt)
                if pattern is None:
                    dt = datetime.fromisoformat(text)
                else:
                    dt = datetime.strptime(text, pattern)
        except ValueError:
            raise ValidationError(f"Timestamp '{value}' tidak sesuai format yang dipilih.")

    if dt.tzinfo is None:
        dt = _attach_local_timezone(dt, tz)
    else:
        dt = dt.astimezone(timezone.utc)
    if dt.microsecond:
        raise ValidationError(
            f"Timestamp {value} memiliki pecahan detik; tidak didukung agar tidak dipotong diam-diam."
        )
    return int(dt.timestamp())


def parse_scope_status(value) -> str:
    if is_blank(value):
        return "in_scope"
    text = clean_text(value).lower()
    reverse = {v.lower(): k for k, v in SCOPE_STATUS.items()}
    if text in SCOPE_STATUS:
        return text
    if text in reverse:
        return reverse[text]
    if text in {"yes", "ya", "true", "1"}:
        return "in_scope"
    if text in {"no", "tidak", "false", "0"}:
        return "excluded"
    raise ValidationError(f"Status scope '{value}' tidak dikenal.")


def parse_price_unit(value) -> str | None:
    if is_blank(value):
        return None
    text = clean_text(value).lower()
    reverse = {v.lower(): k for k, v in PRICE_UNITS.items()}
    if text in PRICE_UNITS:
        return text
    if text in reverse:
        return reverse[text]
    raise ValidationError(f"Satuan harga '{value}' tidak dikenal.")


def parse_statistic_type(value) -> str:
    text = clean_text(value).lower()
    reverse = {v.lower(): k for k, v in STATISTIC_TYPES.items()}
    if text in STATISTIC_TYPES:
        return text
    if text in reverse:
        return reverse[text]
    raise ValidationError(f"Jenis statistik '{value}' tidak dikenal.")


def parse_bool(value, default: bool = True) -> bool:
    if is_blank(value):
        return default
    text = clean_text(value).lower()
    if text in {"1", "true", "ya", "yes", "aktif"}:
        return True
    if text in {"0", "false", "tidak", "no", "nonaktif"}:
        return False
    raise ValidationError(f"Nilai boolean '{value}' tidak dikenal.")


def parse_currency(value) -> str | None:
    if is_blank(value):
        return None
    text = clean_text(value).upper()
    if len(text) != 3 or not text.isalpha():
        raise ValidationError(f"Mata uang '{value}' harus 3 huruf, contoh IDR.")
    return text
