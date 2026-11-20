"""Baca, validasi, dan simpan pengaturan aplikasi (tabel ``settings``).

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.
"""

from __future__ import annotations

from typing import Iterable

from core.db import DEFAULT_SETTINGS, get_conn

BOBOT_KEYS = ("bobot_hadir", "bobot_izin", "bobot_sakit", "bobot_alpa")
AMBANG_KEYS = ("ambang_a", "ambang_b", "ambang_c")

LABEL_BOBOT = {
    "bobot_hadir": "Hadir",
    "bobot_izin": "Izin",
    "bobot_sakit": "Sakit",
    "bobot_alpa": "Alpa",
}

LABEL_AMBANG = {
    "ambang_a": "Ambang A (minimum nilai A)",
    "ambang_b": "Ambang B (minimum nilai B)",
    "ambang_c": "Ambang C (minimum nilai C)",
}


def default_settings() -> dict[str, float]:
    """Nilai bawaan sebagai dict float."""
    return {key: float(value) for key, value in DEFAULT_SETTINGS.items()}


def load_settings() -> dict[str, float]:
    """Baca seluruh pengaturan dari DB sebagai dict float.

    Key yang belum ada di DB diisi dengan nilai bawaan.
    """
    result = default_settings()
    conn = get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    finally:
        conn.close()
    for row in rows:
        key = row["key"]
        if key not in result:
            continue
        try:
            result[key] = float(row["value"])
        except (TypeError, ValueError):
            result[key] = float(DEFAULT_SETTINGS[key])
    return result


def validate_settings(values: dict[str, float]) -> list[str]:
    """Kembalikan daftar pesan error; list kosong berarti valid."""
    errors: list[str] = []
    parsed: dict[str, float] = {}

    for key in BOBOT_KEYS + AMBANG_KEYS:
        if key not in values:
            errors.append(f"Nilai {key} belum diisi.")
            continue
        try:
            parsed[key] = float(values[key])
        except (TypeError, ValueError):
            errors.append(f"Nilai {key} harus berupa angka.")

    if errors:
        return errors

    for key in BOBOT_KEYS:
        if not 0 <= parsed[key] <= 1:
            errors.append(f"Bobot {LABEL_BOBOT[key]} harus antara 0 dan 1.")
    if parsed["bobot_hadir"] <= parsed["bobot_alpa"]:
        errors.append("Bobot Hadir harus lebih besar dari bobot Alpa.")

    for key in AMBANG_KEYS:
        if not 0 <= parsed[key] <= 100:
            errors.append(f"Nilai {LABEL_AMBANG[key]} harus antara 0 dan 100.")
    if not (
        parsed["ambang_a"] > parsed["ambang_b"] > parsed["ambang_c"]
    ):
        errors.append(
            "Ambang harus menurun: ambang A > ambang B > ambang C."
        )

    return errors


def save_settings(values: dict[str, float]) -> dict[str, float]:
    """Validasi lalu simpan pengaturan (upsert).

    Melempar ``ValueError`` berisi semua pesan error bila tidak valid;
    tidak ada yang ditulis ke DB dalam kasus itu.
    """
    errors = validate_settings(values)
    if errors:
        raise ValueError("; ".join(errors))

    normalized = {
        key: float(values[key]) for key in BOBOT_KEYS + AMBANG_KEYS
    }
    rows: Iterable[tuple[str, str]] = [
        (key, _format_number(value)) for key, value in normalized.items()
    ]
    conn = get_conn()
    try:
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            list(rows),
        )
        conn.commit()
    finally:
        conn.close()
    return normalized


def reset_settings() -> dict[str, float]:
    """Kembalikan seluruh pengaturan ke nilai bawaan."""
    defaults = default_settings()
    return save_settings(defaults)


def weighted_score(values: dict[str, float], counts: dict[str, int]) -> float:
    """Skor persentase berbobot dari jumlah status presensi."""
    total = sum(counts.get(status, 0) for status in ("Hadir", "Izin", "Sakit", "Alpa"))
    if total <= 0:
        return 0.0
    bobot = {
        "Hadir": values["bobot_hadir"],
        "Izin": values["bobot_izin"],
        "Sakit": values["bobot_sakit"],
        "Alpa": values["bobot_alpa"],
    }
    poin = sum(bobot[status] * counts.get(status, 0) for status in bobot)
    return round(poin / total * 100, 2)


def predikat(score: float, values: dict[str, float]) -> str:
    """Predikat A/B/C/D berdasarkan ambang yang tersimpan."""
    if score >= values["ambang_a"]:
        return "A"
    if score >= values["ambang_b"]:
        return "B"
    if score >= values["ambang_c"]:
        return "C"
    return "D"


def _format_number(value: float) -> str:
    """Simpan angka rapi: 1.0 -> '1', 0.75 -> '0.75'."""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.4f}".rstrip("0").rstrip(".")
