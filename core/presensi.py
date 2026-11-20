"""Sesi presensi dan pencatatan kehadiran massal (tabel ``sesi`` & ``presensi``).

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Mapping

from core.db import get_conn

STATUS_VALID = ("Hadir", "Izin", "Sakit", "Alpa")
JENIS_VALID = ("Latihan", "Misa", "Tampil")
STATUS_DEFAULT = "Hadir"

class PresensiError(ValueError):
    """Kesalahan validasi data presensi dengan pesan siap tampil."""

def _ke_iso(tanggal: str | date) -> str:
    if isinstance(tanggal, date):
        return tanggal.isoformat()
    try:
        return date.fromisoformat(str(tanggal).strip()).isoformat()
    except ValueError as exc:
        raise PresensiError(
            f"Tanggal {tanggal!r} tidak valid, gunakan format YYYY-MM-DD."
        ) from exc

def _validasi_jenis(jenis: str) -> str:
    text = str(jenis or "").strip()
    for valid in JENIS_VALID:
        if valid.lower() == text.lower():
            return valid
    raise PresensiError(f"Jenis sesi harus salah satu dari {', '.join(JENIS_VALID)}.")

def _validasi_status(status: str) -> str:
    text = str(status or "").strip()
    for valid in STATUS_VALID:
        if valid.lower() == text.lower():
            return valid
    raise PresensiError(f"Status harus salah satu dari {', '.join(STATUS_VALID)}.")

def _baris_sesi(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None

def list_sesi(
    start: str | date | None = None,
    end: str | date | None = None,
    jenis: str | None = None,
) -> list[dict[str, Any]]:
    """Daftar sesi urut tanggal menurun (terbaru dulu)."""
    kondisi: list[str] = []
    params: list[Any] = []
    if start is not None:
        kondisi.append("tanggal >= ?")
        params.append(_ke_iso(start))
    if end is not None:
        kondisi.append("tanggal <= ?")
        params.append(_ke_iso(end))
    if jenis is not None:
        kondisi.append("jenis = ?")
        params.append(_validasi_jenis(jenis))

    query = "SELECT id, tanggal, jenis, catatan FROM sesi"
    if kondisi:
        query += " WHERE " + " AND ".join(kondisi)
    query += " ORDER BY tanggal DESC, id DESC"

    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [_baris_sesi(row) for row in rows]

def get_sesi(sesi_id: int) -> dict[str, Any] | None:
    """Ambil satu sesi berdasarkan id (None bila tidak ada)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, tanggal, jenis, catatan FROM sesi WHERE id = ?", (sesi_id,)
        ).fetchone()
    finally:
        conn.close()
    return _baris_sesi(row)

def get_atau_buat_sesi(
    tanggal: str | date, jenis: str, catatan: str | None = None
) -> int:
    """Kembalikan id sesi untuk (tanggal, jenis), buat baru bila belum ada.

    Bila sesi sudah ada, catatan lama dipertahankan kecuali ``catatan`` diisi.
    """
    tanggal_iso = _ke_iso(tanggal)
    jenis_final = _validasi_jenis(jenis)
    catatan_final = None if catatan is None else str(catatan).strip() or None

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sesi (tanggal, jenis, catatan) VALUES (?, ?, ?) "
            "ON CONFLICT (tanggal, jenis) DO UPDATE SET "
            "catatan = COALESCE(excluded.catatan, sesi.catatan)",
            (tanggal_iso, jenis_final, catatan_final),
        )
        row = conn.execute(
            "SELECT id FROM sesi WHERE tanggal = ? AND jenis = ?",
            (tanggal_iso, jenis_final),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return int(row["id"])

def muat_presensi(sesi_id: int) -> dict[int, str]:
    """Status presensi yang sudah tersimpan untuk sesi, ``{anggota_id: status}``."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT anggota_id, status FROM presensi WHERE sesi_id = ?", (sesi_id,)
        ).fetchall()
    finally:
        conn.close()
    return {int(row["anggota_id"]): row["status"] for row in rows}

def simpan_presensi(
    sesi_id: int,
    status_map: Mapping[int, str],
    catatan: str | None = None,
) -> dict[str, int]:
    """Simpan status presensi massal dalam satu transaksi.

    Hanya anggota aktif yang diterima. Anggota aktif yang tidak ada di
    ``status_map`` dibiarkan apa adanya (tidak dihapus); baris presensi untuk
    anggota yang sudah nonaktif tetap tersimpan sebagai riwayat.

    Kembalikan ringkasan jumlah per status dari ``status_map``.
    """
    if not isinstance(status_map, Mapping):
        raise PresensiError("Data presensi harus berupa dict {anggota_id: status}.")

    bersih: dict[int, str] = {}
    for anggota_id, status in status_map.items():
        try:
            anggota_id_int = int(anggota_id)
        except (TypeError, ValueError) as exc:
            raise PresensiError(f"anggota_id {anggota_id!r} tidak valid.") from exc
        bersih[anggota_id_int] = _validasi_status(status)

    conn = get_conn()
    try:
        sesi = conn.execute("SELECT 1 FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
        if sesi is None:
            raise PresensiError("Sesi presensi tidak ditemukan.")

        if bersih:
            penanda = ",".join("?" * len(bersih))
            valid = {
                int(row["id"])
                for row in conn.execute(
                    f"SELECT id FROM anggota WHERE aktif = 1 AND id IN ({penanda})",
                    list(bersih),
                ).fetchall()
            }
            tidak_valid = sorted(set(bersih) - valid)
            if tidak_valid:
                raise PresensiError(
                    "Anggota tidak ditemukan atau tidak aktif: "
                    + ", ".join(str(i) for i in tidak_valid)
                    + "."
                )
            conn.executemany(
                "INSERT INTO presensi (sesi_id, anggota_id, status) VALUES (?, ?, ?) "
                "ON CONFLICT (sesi_id, anggota_id) DO UPDATE SET status = excluded.status",
                [(sesi_id, anggota_id, status) for anggota_id, status in bersih.items()],
            )

        if catatan is not None:
            conn.execute(
                "UPDATE sesi SET catatan = ? WHERE id = ?",
                (str(catatan).strip() or None, sesi_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    ringkasan = {status: 0 for status in STATUS_VALID}
    for status in bersih.values():
        ringkasan[status] += 1
    return ringkasan

def hapus_sesi(sesi_id: int) -> bool:
    """Hapus sesi; presensi terkait ikut terhapus (ON DELETE CASCADE)."""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM sesi WHERE id = ?", (sesi_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def ringkasan_sesi(sesi_id: int) -> dict[str, int]:
    """Jumlah presensi per status untuk satu sesi (selalu berisi keempat status)."""
    ringkasan = {status: 0 for status in STATUS_VALID}
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS jumlah FROM presensi WHERE sesi_id = ? "
            "GROUP BY status",
            (sesi_id,),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        if row["status"] in ringkasan:
            ringkasan[row["status"]] = int(row["jumlah"])
    return ringkasan

def anggota_aktif() -> list[dict[str, Any]]:
    """Anggota aktif urut nama (NIS, Nama, Suara) untuk layar presensi."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, nis, nama, suara FROM anggota WHERE aktif = 1 "
            "ORDER BY nama COLLATE NOCASE, nis"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]

def rentang_minggu(tanggal: str | date) -> tuple[str, str]:
    """Rentang Senin–Minggu yang memuat ``tanggal`` (format ISO)."""
    dasar = date.fromisoformat(_ke_iso(tanggal))
    senin = dasar - timedelta(days=dasar.weekday())
    return senin.isoformat(), (senin + timedelta(days=6)).isoformat()

def teks_ringkasan(ringkasan: Mapping[str, int]) -> str:
    """Ringkasan satu baris, mis. ``Hadir 12 · Izin 1 · Sakit 0 · Alpa 2``."""
    return " · ".join(f"{status} {ringkasan.get(status, 0)}" for status in STATUS_VALID)

def total_dicatat(ringkasan: Mapping[str, int]) -> int:
    return sum(int(ringkasan.get(status, 0)) for status in STATUS_VALID)
