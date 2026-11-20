"""Cadangkan dan pulihkan seluruh database aplikasi (``data.db``).

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from core.db import DB_PATH, get_conn, init_db

SQLITE_HEADER = b"SQLite format 3\x00"
SQLITE_MIME = "application/x-sqlite3"
TABEL_WAJIB = ("anggota", "sesi", "presensi", "settings")

BACKUP_PATH = DB_PATH.with_name(DB_PATH.name + ".bak")
TMP_PATH = DB_PATH.with_name(DB_PATH.name + ".tmp")

class BackupError(ValueError):
    """Berkas cadangan tidak valid; DB aktif tidak diubah."""

def backup_bytes() -> bytes:
    """Isi ``data.db`` yang konsisten, dibuat lewat SQLite backup API.

    Koneksi sumber ditutup sebelum berkas dibaca sehingga tidak ada tulisan
    yang tertunda (WAL/journal) saat snapshot diambil.
    """
    init_db()
    # readonly=False: sqlite3.Connection.backup menolak servernya readonly.
    src = sqlite3.connect(DB_PATH)
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="spv-backup-", suffix=".db")
    os.close(tmp_fd)
    try:
        dst = sqlite3.connect(tmp_name)
        try:
            src.backup(dst)
        finally:
            dst.close()
        return Path(tmp_name).read_bytes()
    finally:
        src.close()
        Path(tmp_name).unlink(missing_ok=True)

def _validasi(data: bytes) -> None:
    if not data:
        raise BackupError("Berkas cadangan kosong.")
    if not data.startswith(SQLITE_HEADER):
        raise BackupError(
            "Berkas bukan database SQLite yang valid (header 'SQLite format 3' tidak ditemukan)."
        )

    fd, tmp_name = tempfile.mkstemp(prefix="spv-validasi-", suffix=".db")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            # mode=ro mencegah SQLite membuat/menulis file saat validasi.
            conn = sqlite3.connect(Path(tmp_name).as_uri() + "?mode=ro", uri=True)
            try:
                tabel = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                for nama in TABEL_WAJIB:
                    if nama not in tabel:
                        raise BackupError(
                            f"Berkas bukan cadangan aplikasi ini: tabel '{nama}' tidak ditemukan."
                        )
                cek = conn.execute("PRAGMA integrity_check").fetchone()
                if not cek or cek[0] != "ok":
                    raise BackupError("Berkas database rusak (integrity check gagal).")
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"Berkas bukan database SQLite yang valid: {exc}") from exc
    finally:
        Path(tmp_name).unlink(missing_ok=True)

def restore_from_bytes(data: bytes) -> None:
    """Ganti seluruh isi ``data.db`` dengan isi cadangan ``data``.

    Validasi dilakukan lebih dulu; bila gagal melempar ``BackupError``
    (subclass ``ValueError``) tanpa menyentuh DB aktif. Salinan DB aktif
    disimpan ke ``data.db.bak`` sebelum penimpaan atomik via ``os.replace``.
    """
    _validasi(data)

    init_db()
    sumber = get_conn()
    try:
        tujuan = sqlite3.connect(BACKUP_PATH)
        try:
            sumber.backup(tujuan)
        finally:
            tujuan.close()
    finally:
        sumber.close()

    try:
        TMP_PATH.write_bytes(data)
        os.replace(TMP_PATH, DB_PATH)
    except Exception:
        TMP_PATH.unlink(missing_ok=True)
        raise
    init_db()
