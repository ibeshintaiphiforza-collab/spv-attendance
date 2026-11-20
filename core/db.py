"""Akses database SQLite untuk aplikasi presensi Saint Paul Voices.

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai ulang
(misal dari skrip CLI atau pengujian).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"

DEFAULT_SETTINGS = {
    "bobot_hadir": "1",
    "bobot_izin": "0.5",
    "bobot_sakit": "0.5",
    "bobot_alpa": "0",
    "ambang_a": "90",
    "ambang_b": "75",
    "ambang_c": "60",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS anggota (
    id      INTEGER PRIMARY KEY,
    nis     TEXT NOT NULL UNIQUE,
    nama    TEXT NOT NULL,
    kelas   TEXT,
    suara   TEXT NOT NULL CHECK (suara IN ('Sopran', 'Alto', 'Tenor', 'Bass')),
    aktif   INTEGER NOT NULL DEFAULT 1 CHECK (aktif IN (0, 1))
);

CREATE TABLE IF NOT EXISTS sesi (
    id      INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    jenis   TEXT NOT NULL CHECK (jenis IN ('Latihan', 'Misa', 'Tampil')),
    catatan TEXT,
    UNIQUE (tanggal, jenis)
);

CREATE TABLE IF NOT EXISTS presensi (
    id         INTEGER PRIMARY KEY,
    sesi_id    INTEGER NOT NULL REFERENCES sesi (id) ON DELETE CASCADE,
    anggota_id INTEGER NOT NULL REFERENCES anggota (id) ON DELETE CASCADE,
    status     TEXT NOT NULL CHECK (status IN ('Hadir', 'Izin', 'Sakit', 'Alpa')),
    UNIQUE (sesi_id, anggota_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_presensi_anggota ON presensi (anggota_id);
CREATE INDEX IF NOT EXISTS idx_presensi_sesi ON presensi (sesi_id);
CREATE INDEX IF NOT EXISTS idx_anggota_suara ON anggota (suara);
"""


def get_conn() -> sqlite3.Connection:
    """Buat koneksi baru ke data.db dengan foreign key aktif."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Buat schema dan seed settings bawaan. Aman dipanggil berulang."""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            list(DEFAULT_SETTINGS.items()),
        )
        conn.commit()
    finally:
        conn.close()
