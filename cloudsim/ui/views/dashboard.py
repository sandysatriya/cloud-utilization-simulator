import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cloudsim.analysis.stats import interval_phrase, stat_phrase
from cloudsim.services.analysis_service import aggregate_stats
from cloudsim.ui.context import build_analysis, clamp_multiselect, show_quality_summary
from cloudsim.ui.format import flag_labels, local_range, number, pct


METRIC_LABELS = {"cpu": "CPU", "memory": "Memory"}


def _source_labels(analysis, metric: str) -> str:
    batches = analysis.batches_for(metric)
    if not batches:
        return "Tidak ada batch"
    interval = analysis.interval_by_metric.get(metric)
    stat_type = analysis.stat_type_by_metric.get(metric)
    labels = []
    for batch in batches:
        labels.append(stat_phrase("p95", stat_type, interval, batch.statistic_label))
    unique = sorted(set(labels))
    return "; ".join(unique)


def _metric_stats_table(analysis) -> pd.DataFrame:
    rows = []
    for item in analysis.stats:
        rows.append({
            "Kode": item.server.code,
            "Nama": item.server.name,
            "Environment": item.server.environment,
            "Workload": item.server.workload,
            "Metrik": METRIC_LABELS[item.metric],
            "Sampel": item.sample_count,
            "Perkiraan sampel": item.expected_count,
            "Kelengkapan": pct(item.completeness_pct),
            "Rata-rata": number(item.avg),
            "P95": number(item.p95),
            "Maksimum": number(item.max),
            "Flag kualitas": flag_labels(item.flags),
        })
    return pd.DataFrame(rows)


def _series_figure(analysis, metric: str, server_codes: list[str]) -> go.Figure:
    figure = go.Figure()
    for code in server_codes:
        item = analysis.stats_for(code, metric)
        if not item or not item.series:
            continue
        timestamps = pd.to_datetime(
            [ts for ts, _ in item.series], unit="s", utc=True
        ).tz_convert(analysis.display_timezone)
        values = [value for _, value in item.series]
        figure.add_trace(go.Scatter(
            x=timestamps, y=values, mode="lines", name=code,
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:.2f}%<extra>" + code + "</extra>",
        ))
    figure.update_layout(
        xaxis_title=f"Waktu ({analysis.display_timezone})",
        yaxis_title="Utilization (%)",
        yaxis_range=[0, max(105, 100)],
        hovermode="x unified",
        legend_title="Server",
        margin=dict(l=10, r=10, t=30, b=10),
        height=430,
    )
    return figure


def _stats_figure(analysis, metric: str) -> go.Figure:
    rows = [
        item for item in analysis.stats
        if item.metric == metric and item.avg is not None
    ]
    codes = [item.server.code for item in rows]
    figure = go.Figure()
    for stat, label in (("avg", "Rata-rata"), ("p95", "P95"), ("max", "Maksimum")):
        figure.add_trace(go.Bar(
            x=codes, y=[getattr(item, stat) for item in rows], name=label,
        ))
    figure.update_layout(
        barmode="group",
        yaxis_title="Utilization (%)",
        xaxis_title="Server",
        margin=dict(l=10, r=10, t=30, b=10),
        height=430,
    )
    return figure


def _aggregate_table(analysis, metric: str) -> pd.DataFrame:
    rows = []
    methods = [
        ("simple_mean", "Rata-rata sederhana antarserver", "Bukan utilization seluruh kapasitas."),
        ("capacity_weighted_vcpu", "Berbobot vCPU", "Bobot = vCPU server yang memiliki nilai."),
        ("capacity_weighted_ram", "Berbobot RAM", "Bobot = RAM GiB server yang memiliki nilai."),
    ]
    for method, label, note in methods:
        for measure, measure_label in (("avg", "Rata-rata"), ("p95", "P95"), ("max", "Maksimum")):
            result = aggregate_stats(analysis.stats, metric, measure, method)
            rows.append({
                "Metode": label,
                "Ukuran": measure_label,
                "Nilai": result["value"],
                "Server dihitung": result["calculated"],
                "Total server metrik": result["total_servers"],
                "Catatan": note,
            })
    return pd.DataFrame(rows)


def render(filters: dict | None) -> None:
    st.title("Dashboard Utilization")
    st.caption(
        "Statistik deskriptif dari data yang diimpor. Tidak ada rekomendasi resize otomatis; "
        "data yang tidak cukup ditandai."
    )
    analysis = build_analysis(filters)
    if analysis is None:
        return

    st.markdown(
        f"**Periode:** {local_range(analysis.window_start_utc, analysis.window_end_utc, analysis.display_timezone)}"
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Server dalam scope", len(analysis.included_servers))
    col2.metric("Server dikecualikan", len(analysis.exclusions))
    col3.metric("Batch CPU", len(analysis.cpu_batches))
    col4.metric("Batch memory", len(analysis.memory_batches))

    if analysis.warnings:
        for warning in analysis.warnings:
            st.warning(warning)
    show_quality_summary(analysis)

    st.subheader("Ringkasan statistik per server")
    stats_frame = _metric_stats_table(analysis)
    if stats_frame.empty:
        st.info("Tidak ada server dalam scope.")
    else:
        st.dataframe(stats_frame, width="stretch", hide_index=True,
                     column_config={
                         "Kelengkapan": st.column_config.TextColumn(help="Kosong bila interval tidak diketahui."),
                     })

    st.subheader("Grafik")
    metric = st.radio(
        "Metrik grafik", options=["cpu", "memory"],
        format_func=lambda value: METRIC_LABELS[value],
        horizontal=True, key="dash_metric",
    )
    available = [
        item.server.code for item in analysis.stats
        if item.metric == metric and item.series
    ]
    if not available:
        st.info(f"Tidak ada data {METRIC_LABELS[metric]} pada periode ini.")
    else:
        tab_series, tab_stats = st.tabs(["Time series", "Perbandingan statistik"])
        with tab_series:
            default = available[:3]
            clamp_multiselect(f"dash_servers_{metric}", available)
            selected = st.multiselect(
                "Server", options=available, default=default, key=f"dash_servers_{metric}",
            )
            if selected:
                st.plotly_chart(_series_figure(analysis, metric, selected),
                                width="stretch")
            st.caption("Sumber: " + _source_labels(analysis, metric))
        with tab_stats:
            st.plotly_chart(_stats_figure(analysis, metric), width="stretch")
            st.caption(
                "Label sumber: " + _source_labels(analysis, metric)
                + ". P95 dihitung dari nilai sampel yang tersedia."
            )

    with st.expander("Agregasi antarserver"):
        st.caption(
            "Rata-rata sederhana antarserver bukan utilization seluruh kapasitas. "
            "Gunakan metode berbobot dan perhatikan jumlah server yang dapat dihitung."
        )
        aggregate_metric = st.selectbox(
            "Metrik agregasi", options=["cpu", "memory"],
            format_func=lambda value: METRIC_LABELS[value], key="agg_metric",
        )
        frame = _aggregate_table(analysis, aggregate_metric)
        st.dataframe(
            frame, width="stretch", hide_index=True,
            column_config={"Nilai": st.column_config.NumberColumn(format="%.2f")},
        )

    with st.expander("Kualitas data dan pengecualian"):
        quality = stats_frame[
            stats_frame["Flag kualitas"] != "Tidak ada"
        ] if not stats_frame.empty else pd.DataFrame()
        if quality.empty:
            st.success("Tidak ada flag kualitas pada periode ini.")
        else:
            st.dataframe(quality, width="stretch", hide_index=True)
        st.markdown("**Server dikecualikan**")
        if analysis.exclusions:
            st.dataframe(pd.DataFrame([{
                "Kode": item.server_code,
                "Nama": item.server_name,
                "Sumber": "Manual" if item.source == "manual" else "Aturan",
                "Aturan": item.rule_name,
                "Alasan": item.reason,
            } for item in analysis.exclusions]), width="stretch", hide_index=True)
        else:
            st.caption("Tidak ada server dikecualikan.")

    with st.expander("Metode dan batasan"):
        st.markdown(
            "- Rata-rata adalah rata-rata aritmetika sampel pada periode, bukan rata-rata berbobot kapasitas.\n"
            "- P95 memakai interpolasi linear posisi (n-1) x 0,95 (setara pandas/Excel PERCENTILE.INC).\n"
            "- Nilai kosong bukan nol; celah tidak diisi otomatis.\n"
            "- Kelengkapan = jumlah sampel / perkiraan sampel pada periode, hanya bila interval diketahui.\n"
            "- Metadata batch per metrik harus seragam; pencampuran jenis statistik/interval diblokir."
        )
        for metric_key in ("cpu", "memory"):
            st.write(
                f"**{METRIC_LABELS[metric_key]}** — "
                f"{_source_labels(analysis, metric_key)}; "
                f"interval {interval_phrase(analysis.interval_by_metric.get(metric_key))}."
            )
        st.caption(
            "Jika sumber berupa rata-rata per interval, P95 adalah P95 rata-rata per interval, "
            "bukan puncak sesaat. Maksimum juga mengikuti granularitas sumber."
        )
