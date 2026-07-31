-- 活动汇总（每次跑步一行）
CREATE TABLE IF NOT EXISTS activities (
    id            INTEGER PRIMARY KEY,
    filename      TEXT UNIQUE,            -- 去重键（文件名）
    source        TEXT,                   -- fit | tcx | gpx | seed
    sport         TEXT,                   -- running | cycling | ...
    start_time    TEXT NOT NULL,          -- ISO 本地时间
    duration_s    REAL,                   -- elapsed（总耗时）
    timer_s       REAL,                   -- active / moving（计时时间）
    distance_m    REAL,
    avg_speed_mps REAL,
    max_speed_mps REAL,
    avg_hr        REAL,
    max_hr        REAL,
    avg_cadence   REAL,
    avg_power     REAL,
    calories      REAL,
    ele_gain_m    REAL,
    ele_loss_m    REAL,
    avg_grade     REAL
);

-- 每点时间序列（喂图表：心率 / 配速 / 海拔 / 步频）
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL,
    elapsed_s   REAL,
    hr          REAL,
    cadence     REAL,
    speed_mps   REAL,
    distance_m  REAL,
    altitude_m  REAL,
    lat         REAL,
    lon         REAL,
    power       REAL,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

-- 圈（FIT lap / TCX lap）
CREATE TABLE IF NOT EXISTS laps (
    id            INTEGER PRIMARY KEY,
    activity_id   INTEGER NOT NULL,
    lap_index     INTEGER,
    start_time    TEXT,
    duration_s    REAL,
    distance_m    REAL,
    avg_hr        REAL,
    max_hr        REAL,
    avg_speed_mps REAL,
    calories      REAL,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);

-- 单行配置（key/value）
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_records_activity ON records(activity_id);
CREATE INDEX IF NOT EXISTS idx_laps_activity    ON laps(activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_time);
