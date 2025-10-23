-- Migration 002: Feed USA Tables
-- Creates tables for American sports feed functionality

CREATE TABLE IF NOT EXISTS events_cache (
    event_id INTEGER PRIMARY KEY,
    sport_slug TEXT NOT NULL,
    league_slug TEXT NOT NULL,
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    date_utc TEXT NOT NULL,       -- ISO8601 UTC
    status TEXT NOT NULL,         -- pending/live/settled
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS props_monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    bookmakers_csv TEXT NOT NULL,
    stat_filter TEXT,
    player_filter TEXT,
    interval_seconds INTEGER DEFAULT 60,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS props_lines (
    event_id INTEGER NOT NULL,
    bookmaker TEXT NOT NULL,
    stat_name TEXT NOT NULL,
    player TEXT NOT NULL,
    line REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, bookmaker, stat_name, player)
);

CREATE TABLE IF NOT EXISTS props_line_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    bookmaker TEXT NOT NULL,
    stat_name TEXT NOT NULL,
    player TEXT NOT NULL,
    prev_line REAL,
    new_line REAL,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
