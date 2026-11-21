from dataclasses import dataclass, field


@dataclass
class Server:
    id: int
    code: str
    name: str | None
    environment: str
    region: str | None
    workload: str | None
    vcpu: int
    ram_gib: float
    instance_type: str | None
    scope_status: str
    exclusion_reason: str | None
    price_amount: float | None = None
    price_currency: str | None = None
    price_unit: str | None = None
    price_unit_label: str | None = None
    price_source_date: str | None = None
    notes: str | None = None


@dataclass
class Batch:
    id: int
    data_type: str
    file_name: str
    file_sha256: str
    timezone: str | None
    interval_seconds: int | None
    statistic_type: str | None
    statistic_label: str | None
    period_start_utc: int | None
    period_end_utc: int | None
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    imported_at: str
    notes: str | None = None

    @property
    def metric(self) -> str:
        return self.data_type


@dataclass
class Exclusion:
    server_code: str
    server_name: str | None
    source: str
    rule_name: str | None
    reason: str


@dataclass
class MetricStats:
    server: Server
    metric: str
    sample_count: int
    expected_count: int | None
    completeness_pct: float | None
    avg: float | None
    p95: float | None
    max: float | None
    flags: list[str] = field(default_factory=list)
    series: list[tuple[int, float]] = field(default_factory=list)


@dataclass
class AnalysisResult:
    window_start_utc: int
    window_end_utc: int
    display_timezone: str
    formula_version: str
    p95_method: str
    servers: list[Server]
    exclusions: list[Exclusion]
    cpu_batches: list[Batch]
    memory_batches: list[Batch]
    stats: list[MetricStats]
    warnings: list[str]
    stat_type_by_metric: dict[str, str | None]
    interval_by_metric: dict[str, int | None]
    min_samples: int
    min_completeness_pct: float

    @property
    def excluded_codes(self) -> set[str]:
        return {e.server_code for e in self.exclusions}

    @property
    def included_servers(self) -> list[Server]:
        excluded = self.excluded_codes
        return [s for s in self.servers if s.code not in excluded]

    def batches_for(self, metric: str) -> list[Batch]:
        return self.cpu_batches if metric == "cpu" else self.memory_batches

    def stats_for(self, server_code: str, metric: str) -> MetricStats | None:
        for item in self.stats:
            if item.server.code == server_code and item.metric == metric:
                return item
        return None

    def stats_map(self) -> dict[tuple[str, str], MetricStats]:
        return {(s.server.code, s.metric): s for s in self.stats}
