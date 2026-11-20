"""Unduh DataFrame sebagai CSV (UTF-8 BOM) atau Excel (.xlsx) dalam bentuk bytes.

Modul ini sengaja tidak mengimpor streamlit agar dapat dipakai dari CLI.
"""

from __future__ import annotations

import io

import pandas as pd

CSV_MIME = "text/csv"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def to_csv(df: pd.DataFrame) -> bytes:
    """CSV UTF-8 dengan BOM agar nama beraksen tampil benar di Excel."""
    if df is None:
        return b""
    return df.to_csv(index=False).encode("utf-8-sig")

def to_xlsx(df: pd.DataFrame) -> bytes:
    """Berkas Excel (openpyxl) berisi satu sheet dari ``df``."""
    buffer = io.BytesIO()
    data = df if df is not None else pd.DataFrame()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Rekap")
    return buffer.getvalue()
