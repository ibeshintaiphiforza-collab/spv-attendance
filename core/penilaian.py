"""Rekap dan penilaian kehadiran per anggota dan per suara.

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.

Definisi perhitungan, dipakai konsisten di semua fungsi:

* Denominator skor = ``COUNT(*)`` baris presensi anggota pada sesi yang lolos
  filter periode & jenis (bukan jumlah seluruh sesi), sehingga skor = poin
  berbobot / sesi tercatat * 100.
* Anggota tanpa presensi pada periode tetap ditampilkan dengan 0 sesi, skor 0
  dan predikat ``D``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import pandas as pd

from core.anggota import SUARA_VALID
from core.db import get_conn
from core.presensi import JENIS_VALID
from core.settings import load_settings, predikat, weighted_score

STATUS_VALID = ("Hadir", "Izin", "Sakit", "Alpa")

CATATAN_SKOR = (
    "Skor = poin berbobot (sesuai bobot di Pengaturan) / jumlah sesi pada periode "
    "yang tercatat untuk anggota × 100. Anggota tanpa presensi pada periode tampil "
    "dengan 0 sesi, skor 0, dan predikat D."
)

KOLOM_PER_ANGGOTA = [
    "nis",
    "nama",
    "kelas",
    "suara",
    "jumlah_sesi",
    "hadir",
    "izin",
    "sakit",
    "alpa",
    "skor",
    "predikat",
]

KOLOM_PER_SUARA = [
    "suara",
    "jumlah_anggota",
    "jumlah_sesi",
    "total_tercatat",
    "total_hadir",
    "persen_kehadiran",
    "rata_skor",
    "predikat",
]

LABEL_PER_ANGGOTA = {
    "nis": "NIS",
    "nama": "Nama",
    "kelas": "Kelas",
    "suara": "Suara",
    "jumlah_sesi": "Jumlah Sesi",
    "hadir": "Hadir",
    "izin": "Izin",
    "sakit": "Sakit",
    "alpa": "Alpa",
    "skor": "Skor",
    "predikat": "Predikat",
}

LABEL_PER_SUARA = {
    "suara": "Suara",
    "jumlah_anggota": "Jumlah Anggota",
    "jumlah_sesi": "Jumlah Sesi Periode",
    "total_tercatat": "Total Tercatat",
    "total_hadir": "Total Hadir",
    "persen_kehadiran": "Persentase Hadir (%)",
    "rata_skor": "Rata-rata Skor",
    "predikat": "Predikat",
}

def _ke_iso(tanggal: str | date | None) -> str | None:
    if tanggal is None:
        return None
    if isinstance(tanggal, date):
        return tanggal.isoformat()
    return date.fromisoformat(str(tanggal).strip()).isoformat()

def _normalisasi(daftar: Any, valid: tuple[str, ...], label: str) -> list[str]:
    """Normalisasi filter menjadi list nilai baku (list kosong = tanpa filter)."""
    if daftar is None:
        return []
    nilai = [daftar] if isinstance(daftar, str) else list(daftar)
    hasil: list[str] = []
    for item in nilai:
        teks = str(item or "").strip()
        if not teks:
            continue
        for baku in valid:
            if baku.lower() == teks.lower():
                hasil.append(baku)
                break
        else:
            raise ValueError(
                f"{label} {teks!r} tidak valid (pilihan: {', '.join(valid)})."
            )
    return list(dict.fromkeys(hasil))

def _filter_sesi(
    start: str | date | None,
    end: str | date | None,
    jenis: str | Iterable[str] | None,
) -> tuple[list[str], list[Any], int]:
    """Kondisi WHERE filter sesi (alias ``s``) dan jumlah sesi yang lolos filter."""
    kondisi: list[str] = []
    params: list[Any] = []

    start_iso = _ke_iso(start)
    end_iso = _ke_iso(end)
    if start_iso is not None:
        kondisi.append("s.tanggal >= ?")
        params.append(start_iso)
    if end_iso is not None:
        kondisi.append("s.tanggal <= ?")
        params.append(end_iso)
    jenis_final = _normalisasi(jenis, JENIS_VALID, "Jenis sesi")
    if jenis_final:
        kondisi.append(f"s.jenis IN ({','.join('?' * len(jenis_final))})")
        params.extend(jenis_final)

    conn = get_conn()
    try:
        where = f" WHERE {' AND '.join(kondisi)}" if kondisi else ""
        row = conn.execute(
            f"SELECT COUNT(*) AS jumlah FROM sesi s{where}", params
        ).fetchone()
    finally:
        conn.close()
    return kondisi, params, int(row["jumlah"])

def rekap_per_anggota(
    start: str | date | None = None,
    end: str | date | None = None,
    jenis: str | Iterable[str] | None = None,
    aktif_only: bool = False,
    suara: str | Iterable[str] | None = None,
) -> pd.DataFrame:
    """Rekap kehadiran per anggota (DataFrame kolom ``KOLOM_PER_ANGGOTA``)."""
    nilai = load_settings()
    k_sesi, p_sesi, _ = _filter_sesi(start, end, jenis)
    suara_final = _normalisasi(suara, SUARA_VALID, "Suara")

    k_anggota: list[str] = []
    p_anggota: list[Any] = []
    if suara_final:
        k_anggota.append(f"a.suara IN ({','.join('?' * len(suara_final))})")
        p_anggota.extend(suara_final)
    if aktif_only:
        k_anggota.append("a.aktif = 1")

    # Satu query: agregat presensi per anggota digabung LEFT JOIN, sehingga
    # anggota tanpa presensi di periode tetap muncul (jumlah_sesi = 0).
    sub_where = f" WHERE {' AND '.join(k_sesi)}" if k_sesi else ""
    where = f" WHERE {' AND '.join(k_anggota)}" if k_anggota else ""

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT a.nis, a.nama, a.kelas, a.suara, "
            "       COALESCE(r.tercatat, 0) AS jumlah_sesi, "
            "       COALESCE(r.hadir, 0) AS hadir, "
            "       COALESCE(r.izin, 0)  AS izin, "
            "       COALESCE(r.sakit, 0) AS sakit, "
            "       COALESCE(r.alpa, 0)  AS alpa "
            "FROM anggota a "
            "LEFT JOIN ("
            "    SELECT p.anggota_id, COUNT(*) AS tercatat, "
            "           SUM(p.status = 'Hadir') AS hadir, "
            "           SUM(p.status = 'Izin')  AS izin, "
            "           SUM(p.status = 'Sakit') AS sakit, "
            "           SUM(p.status = 'Alpa')  AS alpa "
            "    FROM presensi p JOIN sesi s ON s.id = p.sesi_id"
            f"{sub_where} GROUP BY p.anggota_id"
            ") r ON r.anggota_id = a.id"
            f"{where} "
            "ORDER BY a.nama COLLATE NOCASE, a.nis",
            p_sesi + p_anggota,
        ).fetchall()
    finally:
        conn.close()

    data: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        counts = {
            status: int(item[status.lower()]) for status in STATUS_VALID
        }
        skor = weighted_score(nilai, counts) if int(item["jumlah_sesi"]) else 0.0
        data.append(
            {
                "nis": item["nis"],
                "nama": item["nama"],
                "kelas": item["kelas"],
                "suara": item["suara"],
                # Key internal tidak memakai nama status agar tidak bentrok
                # dengan indexer DataFrame (mis. df.Hadir).
                "jml_hadir": counts["Hadir"],
                "jml_izin": counts["Izin"],
                "jml_sakit": counts["Sakit"],
                "jml_alpa": counts["Alpa"],
                "jumlah_sesi": int(item["jumlah_sesi"]),
                "skor": skor,
                "predikat": predikat(skor, nilai),
            }
        )

    hasil = pd.DataFrame(data)
    if hasil.empty:
        return pd.DataFrame(columns=KOLOM_PER_ANGGOTA)
    return hasil.rename(
        columns={f"jml_{s.lower()}": s.lower() for s in STATUS_VALID}
    )[KOLOM_PER_ANGGOTA]

def rekap_per_suara(
    start: str | date | None = None,
    end: str | date | None = None,
    jenis: str | Iterable[str] | None = None,
) -> pd.DataFrame:
    """Rekap kehadiran per suara (DataFrame kolom ``KOLOM_PER_SUARA``).

    ``jumlah_sesi`` = jumlah sesi pada periode filter. Persentase kehadiran =
    total Hadir / total baris presensi tercatat.
    """
    nilai = load_settings()
    k_sesi, p_sesi, jumlah_sesi = _filter_sesi(start, end, jenis)
    sub_where = f" WHERE {' AND '.join(k_sesi)}" if k_sesi else ""

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT a.suara, COUNT(*) AS jumlah_anggota, "
            "       COALESCE(SUM(r.tercatat), 0) AS total_tercatat, "
            "       COALESCE(SUM(r.hadir), 0) AS total_hadir "
            "FROM anggota a "
            "LEFT JOIN ("
            "    SELECT p.anggota_id, COUNT(*) AS tercatat, "
            "           SUM(p.status = 'Hadir') AS hadir "
            "    FROM presensi p JOIN sesi s ON s.id = p.sesi_id"
            f"{sub_where} GROUP BY p.anggota_id"
            ") r ON r.anggota_id = a.id "
            "GROUP BY a.suara",
            p_sesi,
        ).fetchall()
    finally:
        conn.close()

    per_suara = {row["suara"]: dict(row) for row in rows}
    skor_anggota: dict[str, list[float]] = {}
    for baris in rekap_per_anggota(start=start, end=end, jenis=jenis).to_dict("records"):
        skor_anggota.setdefault(baris["suara"], []).append(float(baris["skor"]))

    data: list[dict[str, Any]] = []
    for suara in SUARA_VALID:
        info = per_suara.get(suara)
        if not info or not int(info["jumlah_anggota"]):
            continue
        tercatat = int(info["total_tercatat"])
        hadir = int(info["total_hadir"])
        daftar_skor = skor_anggota.get(suara, [])
        rata = round(sum(daftar_skor) / len(daftar_skor), 2) if daftar_skor else 0.0
        data.append(
            {
                "suara": suara,
                "jumlah_anggota": int(info["jumlah_anggota"]),
                "jumlah_sesi": jumlah_sesi,
                "total_tercatat": tercatat,
                "total_hadir": hadir,
                "persen_kehadiran": (
                    round(hadir / tercatat * 100, 2) if tercatat else 0.0
                ),
                "rata_skor": rata,
                "predikat": predikat(rata, nilai),
            }
        )

    return pd.DataFrame(data, columns=KOLOM_PER_SUARA)

def label_per_anggota(df: pd.DataFrame) -> pd.DataFrame:

    """Salin rekap per anggota dengan judul kolom bahasa Indonesia."""
    return df.rename(columns=LABEL_PER_ANGGOTA)

def label_per_suara(df: pd.DataFrame) -> pd.DataFrame:
    """Salin rekap per suara dengan judul kolom bahasa Indonesia."""
    return df.rename(columns=LABEL_PER_SUARA)
