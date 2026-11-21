"""Helper tampilan angka dan waktu (bahasa Indonesia)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from cloudsim.enums import ESTIMATE_FLAGS, QUALITY_FLAGS


def number(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{number(value, digits)}%"


def pp(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{number(value, digits)} pp"


def relative(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{number(value, digits)}%"


def local_time(ts, tz_name: str) -> str:
    if ts is None:
        return "—"
    return datetime.fromtimestamp(int(ts), ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")


def local_range(start_utc, end_utc, tz_name: str) -> str:
    return f"{local_time(start_utc, tz_name)} s.d. {local_time(end_utc, tz_name)} ({tz_name})"


def flag_labels(flags: list[str] | None) -> str:
    if not flags:
        return "Tidak ada"
    return ", ".join(QUALITY_FLAGS.get(flag, flag) for flag in flags)


def estimate_label(flag: str) -> str:
    return ESTIMATE_FLAGS.get(flag, flag)
