PRAGMA foreign_keys = ON;

CREATE TABLE app_setting (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE server (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    server_code        TEXT NOT NULL COLLATE NOCASE,
    name               TEXT,
    environment        TEXT NOT NULL,
    region             TEXT,
    workload           TEXT,
    vcpu               INTEGER NOT NULL CHECK (vcpu > 0),
    ram_gib            REAL NOT NULL CHECK (ram_gib > 0),
    instance_type      TEXT,
    scope_status       TEXT NOT NULL DEFAULT 'in_scope'
                       CHECK (scope_status IN ('in_scope','excluded')),
    exclusion_reason   TEXT,
    price_amount       REAL CHECK (price_amount IS NULL OR price_amount >= 0),
    price_currency     TEXT,
    price_unit         TEXT CHECK (price_unit IS NULL OR price_unit IN
                       ('per_hour','per_month','per_vcpu_hour','per_gib_month','other')),
    price_unit_label   TEXT,
    price_source_date  TEXT,
    notes              TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    CHECK (scope_status <> 'excluded'
           OR (exclusion_reason IS NOT NULL AND length(trim(exclusion_reason)) > 0)),
    CHECK (price_amount IS NULL OR (price_currency IS NOT NULL
           AND price_unit IS NOT NULL AND price_source_date IS NOT NULL)),
    CHECK (price_amount IS NOT NULL OR (price_currency IS NULL
           AND price_unit IS NULL AND price_unit_label IS NULL
           AND price_source_date IS NULL)),
    CHECK (price_currency IS NULL OR (length(price_currency) = 3
           AND price_currency = upper(price_currency))),
    CHECK (price_unit <> 'other' OR price_unit_label IS NOT NULL)
);

CREATE UNIQUE INDEX ux_server_code ON server(server_code COLLATE NOCASE);
CREATE INDEX ix_server_env ON server(environment);

CREATE TABLE scope_rule (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    dimension    TEXT NOT NULL
                 CHECK (dimension IN ('environment','workload','region','server')),
    match_value  TEXT NOT NULL,
    reason       TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    active       INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE import_batch (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type        TEXT NOT NULL
                     CHECK (data_type IN ('inventory','cpu','memory')),
    file_name        TEXT NOT NULL,
    file_sha256      TEXT NOT NULL,
    timezone         TEXT,
    interval_seconds INTEGER CHECK (interval_seconds IS NULL OR interval_seconds > 0),
    statistic_type   TEXT CHECK (statistic_type IN ('average','maximum','other')),
    statistic_label  TEXT,
    period_start_utc INTEGER,
    period_end_utc   INTEGER,
    total_rows       INTEGER NOT NULL DEFAULT 0,
    accepted_rows    INTEGER NOT NULL DEFAULT 0,
    rejected_rows    INTEGER NOT NULL DEFAULT 0,
    imported_at      TEXT NOT NULL,
    notes            TEXT,
    CHECK (data_type = 'inventory' OR timezone IS NOT NULL),
    CHECK (data_type = 'inventory' OR statistic_type IS NOT NULL),
    CHECK (statistic_type <> 'other' OR statistic_label IS NOT NULL)
);

CREATE TABLE utilization_sample (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id  INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    server_id INTEGER NOT NULL REFERENCES server(id) ON DELETE RESTRICT,
    metric    TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    ts_utc    INTEGER NOT NULL,
    value     REAL NOT NULL CHECK (value >= 0 AND value <= 100)
);

CREATE UNIQUE INDEX ux_sample_key ON utilization_sample(metric, server_id, ts_utc);
CREATE INDEX ix_sample_server_time ON utilization_sample(server_id, metric, ts_utc);

CREATE TABLE import_issue (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    severity TEXT NOT NULL CHECK (severity IN ('error','warning')),
    code     TEXT NOT NULL,
    row_ref  TEXT,
    detail   TEXT NOT NULL
);

CREATE TABLE baseline (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    window_start_utc  INTEGER NOT NULL,
    window_end_utc    INTEGER NOT NULL CHECK (window_end_utc > window_start_utc),
    display_timezone  TEXT NOT NULL,
    formula_version   TEXT NOT NULL,
    notes             TEXT
);

CREATE TABLE baseline_source (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id      INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    metric           TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    batch_id         INTEGER,
    file_name        TEXT NOT NULL,
    file_sha256      TEXT NOT NULL,
    timezone         TEXT NOT NULL,
    interval_seconds INTEGER,
    statistic_type   TEXT NOT NULL,
    statistic_label  TEXT,
    data_start_utc   INTEGER,
    data_end_utc     INTEGER,
    sample_count     INTEGER NOT NULL
);

CREATE TABLE baseline_exclusion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    server_code TEXT NOT NULL,
    server_name TEXT,
    source      TEXT NOT NULL CHECK (source IN ('manual','rule')),
    rule_name   TEXT,
    reason      TEXT NOT NULL
);

CREATE TABLE baseline_server_stat (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id      INTEGER NOT NULL REFERENCES baseline(id) ON DELETE CASCADE,
    server_code      TEXT NOT NULL,
    environment      TEXT,
    workload         TEXT,
    vcpu             INTEGER NOT NULL,
    ram_gib          REAL NOT NULL,
    metric           TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    sample_count     INTEGER NOT NULL CHECK (sample_count >= 0),
    completeness_pct REAL,
    avg_value        REAL,
    p95_value        REAL,
    max_value        REAL,
    quality_flags    TEXT,
    UNIQUE (baseline_id, server_code, metric)
);

CREATE TABLE simulation (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    server_code           TEXT NOT NULL,
    server_name           TEXT,
    environment           TEXT,
    region                TEXT,
    workload              TEXT,
    window_start_utc      INTEGER NOT NULL,
    window_end_utc        INTEGER NOT NULL CHECK (window_end_utc > window_start_utc),
    display_timezone      TEXT NOT NULL,
    statistic_type        TEXT NOT NULL,
    statistic_label       TEXT,
    interval_seconds      INTEGER,
    source_batch_snapshot TEXT,
    source_vcpu           INTEGER NOT NULL CHECK (source_vcpu > 0),
    source_ram_gib        REAL NOT NULL CHECK (source_ram_gib > 0),
    target_vcpu           INTEGER NOT NULL CHECK (target_vcpu > 0),
    target_ram_gib        REAL NOT NULL CHECK (target_ram_gib > 0),
    target_instance_type  TEXT,
    warning_threshold_pct REAL NOT NULL CHECK (warning_threshold_pct > 0
                            AND warning_threshold_pct <= 100),
    completeness_pct      REAL,
    data_sufficient       INTEGER NOT NULL CHECK (data_sufficient IN (0,1)),
    formula_version       TEXT NOT NULL,
    target_price_amount   REAL CHECK (target_price_amount IS NULL
                            OR target_price_amount >= 0),
    target_price_currency TEXT,
    target_price_unit     TEXT CHECK (target_price_unit IS NULL
                            OR target_price_unit IN
                            ('per_hour','per_month','per_vcpu_hour','per_gib_month','other')),
    target_price_unit_label TEXT,
    target_price_source_date TEXT,
    notes                 TEXT,
    CHECK (target_price_amount IS NULL OR (target_price_currency IS NOT NULL
           AND target_price_unit IS NOT NULL AND target_price_source_date IS NOT NULL)),
    CHECK (target_price_currency IS NULL OR (length(target_price_currency) = 3
           AND target_price_currency = upper(target_price_currency))),
    CHECK (target_price_unit <> 'other' OR target_price_unit_label IS NOT NULL)
);

CREATE TABLE simulation_result (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id INTEGER NOT NULL REFERENCES simulation(id) ON DELETE CASCADE,
    metric        TEXT NOT NULL CHECK (metric IN ('cpu','memory')),
    stat_name     TEXT NOT NULL CHECK (stat_name IN ('avg','p95','max')),
    before_value  REAL,
    after_value   REAL,
    flag          TEXT NOT NULL CHECK (flag IN
                  ('normal','near_threshold','over_100','insufficient_data','not_available')),
    UNIQUE (simulation_id, metric, stat_name)
);

CREATE TABLE kpi_definition (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'unconfigured'
                        CHECK (status IN ('unconfigured','draft','approved')),
    metric              TEXT CHECK (metric IN ('cpu','memory')),
    measure             TEXT CHECK (measure IN ('avg','p95','max')),
    aggregate_method    TEXT CHECK (aggregate_method IN
                        ('none','simple_mean','capacity_weighted_vcpu','capacity_weighted_ram')),
    operator            TEXT CHECK (operator IN ('lte','gte','between')),
    target_value        REAL,
    target_value_upper  REAL,
    unit                TEXT NOT NULL DEFAULT 'percent' CHECK (unit = 'percent'),
    scope_mode          TEXT NOT NULL DEFAULT 'current_scope'
                        CHECK (scope_mode IN ('current_scope','baseline_scope')),
    baseline_id         INTEGER REFERENCES baseline(id) ON DELETE SET NULL,
    approved_at         TEXT,
    formula_version     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    CHECK (status <> 'approved' OR (metric IS NOT NULL AND measure IS NOT NULL
           AND aggregate_method IS NOT NULL AND operator IS NOT NULL
           AND target_value IS NOT NULL AND approved_at IS NOT NULL)),
    CHECK (operator <> 'between' OR target_value_upper IS NOT NULL),
    CHECK (scope_mode <> 'baseline_scope' OR baseline_id IS NOT NULL),
    CHECK (target_value_upper IS NULL OR target_value_upper >= target_value)
);

CREATE TABLE kpi_threshold (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kpi_id    INTEGER NOT NULL REFERENCES kpi_definition(id) ON DELETE CASCADE,
    label     TEXT NOT NULL,
    min_value REAL,
    max_value REAL,
    meaning   TEXT,
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value)
);

CREATE INDEX ix_baseline_source ON baseline_source(baseline_id);
CREATE INDEX ix_baseline_stat ON baseline_server_stat(baseline_id, server_code);
CREATE INDEX ix_simulation_server ON simulation(server_code);
CREATE INDEX ix_issue_batch ON import_issue(batch_id, severity);
