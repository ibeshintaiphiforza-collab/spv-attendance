"""CRUD anggota dan import massal dari DataFrame (tabel ``anggota``).

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from core.db import get_conn

SUARA_VALID = ("Sopran", "Alto", "Tenor", "Bass")

# Kolom import -> alias yang diterima (sudah dinormalisasi: huruf kecil).
KOLOM_IMPORT = {
    "nis": ("nis",),
    "nama": ("nama", "nama lengkap", "name"),
    "kelas": ("kelas", "class"),
    "suara": ("suara", "voice", "stem"),
    "aktif": ("aktif", "status aktif", "active"),
}

_SPASI = re.compile(r"\s+")


class AnggotaError(ValueError):
    """Kesalahan validasi data anggota dengan pesan siap tampil."""


def _rapikan_nama(value: Any) -> str:
    return _SPASI.sub(" ", str(value)).strip() if value is not None else ""


def _rapikan_nis(value: Any) -> str:
    if value is None:
        return ""
    # Excel kadang membaca NIS numerik sebagai 12345.0.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _normalisasi_suara(value: Any) -> str | None:
    text = _rapikan_nama(value).lower()
    if not text:
        return None
    for suara in SUARA_VALID:
        if suara.lower() == text:
            return suara
    return None


def _normalisasi_aktif(value: Any) -> int | None:
    text = _rapikan_nama(value).lower()
    if not text:
        return None
    if text in ("1", "ya", "y", "true", "aktif", "active", "yes"):
        return 1
    if text in ("0", "tidak", "t", "false", "nonaktif", "non aktif", "inactive", "no"):
        return 0
    raise AnggotaError(f"nilai kolom Aktif tidak dikenali: {value!r}")


def _validasi(suara: Any) -> str:
    hasil = _normalisasi_suara(suara)
    if hasil is None:
        raise AnggotaError(
            f"Suara harus salah satu dari {', '.join(SUARA_VALID)}."
        )
    return hasil


def _baris_ke_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["aktif"] = bool(data["aktif"])
    return data


def _sisipkan(conn: sqlite3.Connection, nis: str, nama: str, kelas: str, suara: str) -> int:
    try:
        cur = conn.execute(
            "INSERT INTO anggota (nis, nama, kelas, suara) VALUES (?, ?, ?, ?)",
            (nis, nama, kelas, suara),
        )
    except sqlite3.IntegrityError as exc:
        raise AnggotaError(f"NIS {nis} sudah terdaftar.") from exc
    return int(cur.lastrowid)


def _perbarui(
    conn: sqlite3.Connection,
    anggota_id: int,
    nis: str,
    nama: str,
    kelas: str,
    suara: str,
    aktif: int | None = None,
) -> None:
    try:
        if aktif is None:
            conn.execute(
                "UPDATE anggota SET nis = ?, nama = ?, kelas = ?, suara = ? WHERE id = ?",
                (nis, nama, kelas, suara, anggota_id),
            )
        else:
            conn.execute(
                "UPDATE anggota SET nis = ?, nama = ?, kelas = ?, suara = ?, aktif = ? "
                "WHERE id = ?",
                (nis, nama, kelas, suara, aktif, anggota_id),
            )
    except sqlite3.IntegrityError as exc:
        raise AnggotaError(f"NIS {nis} sudah dipakai anggota lain.") from exc


def list_anggota(aktif_only: bool = False, suara: str | None = None) -> list[dict[str, Any]]:
    """Daftar anggota, urut nama. Filter opsional status aktif dan suara."""
    query = "SELECT id, nis, nama, kelas, suara, aktif FROM anggota"
    kondisi: list[str] = []
    params: list[Any] = []
    if aktif_only:
        kondisi.append("aktif = 1")
    if suara:
        suara_final = _validasi(suara)
        kondisi.append("suara = ?")
        params.append(suara_final)
    if kondisi:
        query += " WHERE " + " AND ".join(kondisi)
    query += " ORDER BY nama COLLATE NOCASE, nis"

    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [_baris_ke_dict(row) for row in rows]


def get_anggota(anggota_id: int) -> dict[str, Any] | None:
    """Ambil satu anggota berdasarkan id (None bila tidak ada)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, nis, nama, kelas, suara, aktif FROM anggota WHERE id = ?",
            (anggota_id,),
        ).fetchone()
    finally:
        conn.close()
    return _baris_ke_dict(row)


def tambah_anggota(nis: str, nama: str, kelas: str | None, suara: str) -> int:
    """Tambah anggota baru; kembalikan id. Melempar AnggotaError bila tidak valid."""
    nis_final = _rapikan_nis(nis)
    nama_final = _rapikan_nama(nama)
    if not nis_final:
        raise AnggotaError("NIS wajib diisi.")
    if not nama_final:
        raise AnggotaError("Nama wajib diisi.")
    suara_final = _validasi(suara)

    conn = get_conn()
    try:
        anggota_id = _sisipkan(conn, nis_final, nama_final, _rapikan_nama(kelas), suara_final)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return anggota_id


def edit_anggota(
    anggota_id: int,
    nis: str,
    nama: str,
    kelas: str | None,
    suara: str,
) -> None:
    """Perbarui data anggota; status aktif tidak diubah."""
    if get_anggota(anggota_id) is None:
        raise AnggotaError("Anggota tidak ditemukan.")
    nis_final = _rapikan_nis(nis)
    nama_final = _rapikan_nama(nama)
    if not nis_final:
        raise AnggotaError("NIS wajib diisi.")
    if not nama_final:
        raise AnggotaError("Nama wajib diisi.")
    suara_final = _validasi(suara)

    conn = get_conn()
    try:
        _perbarui(conn, anggota_id, nis_final, nama_final, _rapikan_nama(kelas), suara_final)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_aktif(anggota_id: int, aktif: bool) -> None:
    """Ubah status aktif tanpa menghapus data presensi."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE anggota SET aktif = ? WHERE id = ?", (1 if aktif else 0, anggota_id)
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise AnggotaError("Anggota tidak ditemukan.")
        conn.commit()
    finally:
        conn.close()


def hapus_anggota(anggota_id: int) -> str:
    """Hapus anggota permanen; bila sudah punya presensi, nonaktifkan saja.

    ``presensi`` memakai ON DELETE CASCADE sehingga penghapusan akan ikut
    menghapus riwayat kehadiran. Untuk menjaga data historis, anggota yang
    sudah memiliki riwayat hanya dinonaktifkan. Kembalikan aksi yang dilakukan:
    ``"dihapus"`` atau ``"dinonaktifkan"``.
    """
    conn = get_conn()
    try:
        ada = conn.execute("SELECT 1 FROM anggota WHERE id = ?", (anggota_id,)).fetchone()
        if ada is None:
            raise AnggotaError("Anggota tidak ditemukan.")
        punya_presensi = conn.execute(
            "SELECT 1 FROM presensi WHERE anggota_id = ? LIMIT 1", (anggota_id,)
        ).fetchone()
        if punya_presensi is not None:
            conn.execute("UPDATE anggota SET aktif = 0 WHERE id = ?", (anggota_id,))
            aksi = "dinonaktifkan"
        else:
            conn.execute("DELETE FROM anggota WHERE id = ?", (anggota_id,))
            aksi = "dihapus"
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return aksi


def _normalisasi_kolom(df) -> dict[str, str]:
    """Peta kolom asli -> kolom baku (nis/nama/kelas/suara/aktif)."""
    peta: dict[str, str] = {}
    for asli in df.columns:
        kunci = _SPASI.sub(" ", str(asli)).strip().lower()
        for baku, alias in KOLOM_IMPORT.items():
            if kunci in alias:
                peta[asli] = baku
                break
    return peta


def import_anggota(df, default_suara: str | None = None) -> dict[str, Any]:
    """Upsert anggota dari DataFrame berbasis NIS dalam satu transaksi.

    Kolom yang dikenali: NIS, Nama, Kelas, Suara (opsional), Aktif (opsional).
    NIS yang sudah ada diperbarui; status aktif hanya diubah bila kolom
    ``Aktif`` tersedia. Duplikat NIS dalam file yang sama: baris terakhir
    menang dan tidak membuat baris ganda.

    Kembalikan dict: ``ditambah``, ``diperbarui``, ``dilewati`` (baris dengan
    NIS kosong), ``gagal`` (list ``{"baris", "nis", "alasan"}``), ``total``.
    """
    if df is None or len(df.index) == 0:
        return {
            "ditambah": 0,
            "diperbarui": 0,
            "dilewati": 0,
            "gagal": [],
            "duplikat_file": [],
            "total": 0,
            "pesan": "Tidak ada baris data yang bisa diimpor.",
        }

    peta = _normalisasi_kolom(df)

    default_final: str | None = None
    if default_suara:
        default_final = _normalisasi_suara(default_suara)
        if default_final is None:
            raise AnggotaError(
                f"Suara default harus salah satu dari {', '.join(SUARA_VALID)}."
            )
    if "suara" not in peta.values() and default_final is None:
        raise AnggotaError(
            "Kolom Suara tidak ditemukan. Tambahkan kolom Suara atau pilih suara default."
        )

    # Baris 2 = data pertama (baris 1 adalah header di file).
    kandidat: dict[str, dict[str, Any]] = {}
    gagal: list[dict[str, Any]] = []
    dilewati = 0
    nis_ganda: set[str] = set()
    duplikat_file: list[str] = []

    for posisi, (_, baris) in enumerate(df.iterrows(), start=2):
        nilai = {baku: baris[asli] for asli, baku in peta.items()}
        nis = _rapikan_nis(nilai.get("nis"))
        nama = _rapikan_nama(nilai.get("nama"))
        kelas = _rapikan_nama(nilai.get("kelas"))

        if not nis or nis.lower() == "nan":
            dilewati += 1
            gagal.append(
                {"baris": posisi, "nis": "", "alasan": "NIS kosong, baris dilewati."}
            )
            continue
        if nis in nis_ganda:
            duplikat_file.append(nis)
        else:
            nis_ganda.add(nis)
        if not nama or nama.lower() == "nan":
            gagal.append({"baris": posisi, "nis": nis, "alasan": "Nama kosong."})
            continue

        nilai_suara = nilai.get("suara")
        suara = None
        if nilai_suara is not None and _rapikan_nama(nilai_suara).lower() != "nan":
            suara = _normalisasi_suara(nilai_suara)
            if suara is None:
                gagal.append(
                    {
                        "baris": posisi,
                        "nis": nis,
                        "alasan": (
                            f"Suara {_rapikan_nama(nilai_suara)!r} tidak valid "
                            f"(pilihan: {', '.join(SUARA_VALID)})."
                        ),
                    }
                )
                continue
        if suara is None:
            suara = default_final
        if suara is None:
            gagal.append(
                {"baris": posisi, "nis": nis, "alasan": "Suara kosong dan tidak ada default."}
            )
            continue

        try:
            aktif = _normalisasi_aktif(nilai.get("aktif"))
        except AnggotaError as exc:
            gagal.append({"baris": posisi, "nis": nis, "alasan": str(exc)})
            continue

        # Duplikat NIS dalam file: baris terakhir menang.
        kandidat[nis] = {
            "nis": nis,
            "nama": nama,
            "kelas": kelas,
            "suara": suara,
            "aktif": aktif,
        }

    ditambah = 0
    diperbarui = 0
    conn = get_conn()
    try:
        ada = {
            row["nis"]: row["id"]
            for row in conn.execute("SELECT id, nis FROM anggota").fetchall()
        }
        for data in kandidat.values():
            anggota_id = ada.get(data["nis"])
            try:
                if anggota_id is None:
                    ada[data["nis"]] = _sisipkan(
                        conn, data["nis"], data["nama"], data["kelas"], data["suara"]
                    )
                    ditambah += 1
                else:
                    _perbarui(
                        conn,
                        anggota_id,
                        data["nis"],
                        data["nama"],
                        data["kelas"],
                        data["suara"],
                        data["aktif"],
                    )
                    diperbarui += 1
            except AnggotaError as exc:
                gagal.append({"baris": "-", "nis": data["nis"], "alasan": str(exc)})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    total = ditambah + diperbarui
    if total and gagal:
        pesan = (
            f"{total} baris berhasil diimpor, {len(gagal)} baris gagal atau dilewati."
        )
    elif total:
        pesan = f"{total} baris berhasil diimpor."
    else:
        pesan = "Tidak ada baris yang berhasil diimpor."
    if duplikat_file:
        pesan += (
            f" NIS ganda dalam file ({', '.join(sorted(set(duplikat_file)))}): "
            "baris terakhir dipakai, tidak ada duplikat tersimpan."
        )
    return {
        "ditambah": ditambah,
        "diperbarui": diperbarui,
        "dilewati": dilewati,
        "gagal": gagal,
        "duplikat_file": duplikat_file,
        "total": total,
        "pesan": pesan,
    }
