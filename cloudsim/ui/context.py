from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from cloudsim.errors import AppError
from cloudsim.services import analysis_service, batch_service, settings_service


def _local_date(ts, tz_name: str) -> date | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), ZoneInfo(tz_name)).date()


def _midnight_epoch(day: date, tz_name: str) -> int:
    return int(datetime.combine(day, time.min, tzinfo=ZoneInfo(tz_name)).timestamp())


def _default_ids(batches) -> list[int]:
    if not batches:
        return []
    newest = max(batches, key=lambda b: b.id)
    signature = (newest.statistic_type, newest.interval_seconds)
    return [
        b.id for b in batches
        if (b.statistic_type, b.interval_seconds) == signature
    ]


def _reset_filter_state() -> None:
    for key in ("f_start_date", "f_end_date", "f_cpu_batches", "f_memory_batches"):
        if key in st.session_state:
            del st.session_state[key]


def normalize_selection(key: str, options: list, default=None) -> None:
    """Pastikan nilai widget pilihan masih ada sebelum widget dibuat."""
    if not options:
        return
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = options[0] if default is None else default


def clamp_multiselect(key: str, options: list) -> None:
    if key in st.session_state:
        st.session_state[key] = [value for value in st.session_state[key] if value in options]


def render_filters() -> dict | None:
    st.sidebar.subheader("Periode analisis")
    batches = batch_service.list_batches()
    cpu = [b for b in batches if b.data_type == "cpu"]
    memory = [b for b in batches if b.data_type == "memory"]
    settings = settings_service.get_settings()
    tz_name = settings["display_timezone"]

    all_ts = cpu + memory
    available_dates = [
        day for batch in all_ts
        for day in (_local_date(batch.period_start_utc, tz_name),
                    _local_date(batch.period_end_utc, tz_name))
        if day is not None
    ]
    if available_dates:
        default_start = min(available_dates)
        default_end = max(available_dates)
        st.sidebar.caption(
            f"Data tersedia: {default_start.isoformat()} s.d. {default_end.isoformat()} ({tz_name})"
        )
    else:
        default_end = date.today()
        default_start = default_end - timedelta(days=7)
        st.sidebar.info("Belum ada batch time series. Impor data terlebih dahulu.")

    if "f_start_date" not in st.session_state:
        st.session_state["f_start_date"] = default_start
    if "f_end_date" not in st.session_state:
        st.session_state["f_end_date"] = default_end

    col_a, col_b = st.sidebar.columns(2)
    start_date = col_a.date_input("Awal", key="f_start_date")
    end_date = col_b.date_input("Akhir", key="f_end_date")

    def batch_label(batch_id: int) -> str:
        for batch in all_ts:
            if batch.id == batch_id:
                interval = f"{batch.interval_seconds} dtk" if batch.interval_seconds else "tanpa interval"
                return f"#{batch.id} {batch.file_name} ({batch.statistic_type}, {interval})"
        return f"#{batch_id}"

    if "f_cpu_batches" not in st.session_state:
        st.session_state["f_cpu_batches"] = _default_ids(cpu)
    if "f_memory_batches" not in st.session_state:
        st.session_state["f_memory_batches"] = _default_ids(memory)
    valid_cpu = {b.id for b in cpu}
    valid_memory = {b.id for b in memory}
    st.session_state["f_cpu_batches"] = [
        i for i in st.session_state["f_cpu_batches"] if i in valid_cpu
    ]
    st.session_state["f_memory_batches"] = [
        i for i in st.session_state["f_memory_batches"] if i in valid_memory
    ]
    cpu_ids = st.sidebar.multiselect(
        "Batch CPU", options=[b.id for b in cpu], format_func=batch_label,
        key="f_cpu_batches",
    )
    memory_ids = st.sidebar.multiselect(
        "Batch memory", options=[b.id for b in memory], format_func=batch_label,
        key="f_memory_batches",
    )
    if st.sidebar.button("Reset filter ke data terbaru", width="stretch"):
        _reset_filter_state()
        st.rerun()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "cpu_batch_ids": cpu_ids,
        "memory_batch_ids": memory_ids,
        "display_timezone": tz_name,
        "min_samples": int(settings["min_samples"]),
        "min_completeness_pct": float(settings["min_completeness_pct"]),
        "warning_threshold_pct": float(settings["warning_threshold_pct"]),
    }


def build_analysis(filters: dict | None, *, show_error: bool = True):
    if filters is None:
        return None
    if not filters["cpu_batch_ids"] and not filters["memory_batch_ids"]:
        if show_error:
            st.warning("Pilih minimal satu batch CPU atau memory pada sidebar.")
        return None
    if filters["end_date"] < filters["start_date"]:
        if show_error:
            st.error("Tanggal akhir tidak boleh sebelum tanggal awal.")
        return None
    start_utc = _midnight_epoch(filters["start_date"], filters["display_timezone"])
    if filters["end_date"] == date.max:
        end_utc = start_utc
    else:
        end_utc = _midnight_epoch(filters["end_date"] + timedelta(days=1), filters["display_timezone"])
    try:
        return analysis_service.analyze(
            start_utc,
            end_utc,
            filters["cpu_batch_ids"],
            filters["memory_batch_ids"],
            filters["display_timezone"],
        )
    except AppError as exc:
        if show_error:
            st.error(str(exc))
        return None


def show_quality_summary(analysis) -> None:
    if not analysis.stats:
        st.info("Tidak ada server dalam scope untuk dianalisis.")
        return
    flagged = [
        item for item in analysis.stats
        if any(flag not in {"metric_unavailable"} for flag in item.flags)
    ]
    unavailable = [item for item in analysis.stats if "metric_unavailable" in item.flags]
    if flagged:
        names = sorted({f"{i.server.code}/{i.metric.upper()}" for i in flagged})
        st.warning(
            f"{len(names)} pasangan server-metrik memiliki catatan kualitas data: "
            + ", ".join(names[:10])
            + (" ..." if len(names) > 10 else "")
        )
    if unavailable:
        st.info(
            f"{len(unavailable)} pasangan server-metrik tidak memiliki batch sumber "
            "dan ditandai Tidak tersedia (bukan nol)."
        )
