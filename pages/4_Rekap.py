from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from core.anggota import SUARA_VALID
from core.db import init_db
from core.export import CSV_MIME, XLSX_MIME, to_csv, to_xlsx
from core.penilaian import (
    CATATAN_SKOR,
    label_per_anggota,
    label_per_suara,
    rekap_per_anggota,
    rekap_per_suara,
)
from core.presensi import JENIS_VALID

st.set_page_config(page_title="Rekap | Saint Paul Voices", page_icon="📊", layout="wide")
init_db()

st.title("📊 Rekap & Penilaian Kehadiran")
st.caption("Rekap kehadiran per anggota dan per suara untuk periode dan jenis sesi tertentu.")

hari_ini = date.today()
awal_bulan = hari_ini.replace(day=1)

col_periode, col_jenis, col_suara = st.columns([1.6, 1, 1])
with col_periode:
    rentang = st.date_input(
        "Periode (mulai – akhir)",
        value=(awal_bulan, hari_ini),
        format="YYYY-MM-DD",
        key="rekap_periode",
    )
with col_jenis:
    jenis_pilih = st.multiselect(
        "Jenis sesi",
        list(JENIS_VALID),
        placeholder="Semua jenis",
        key="rekap_jenis",
    )
with col_suara:
    suara_pilih = st.multiselect(
        "Suara",
        list(SUARA_VALID),
        placeholder="Semua suara",
        key="rekap_suara",
    )

if isinstance(rentang, (tuple, list)):
    start, end = (rentang[0], rentang[1] if len(rentang) > 1 else rentang[0])
else:
    start, end = rentang, rentang

if start and end and start > end:
    st.error("Tanggal awal tidak boleh melewati tanggal akhir.")
    st.stop()

try:
    df_anggota = rekap_per_anggota(
        start=start,
        end=end,
        jenis=jenis_pilih or None,
        suara=suara_pilih or None,
    )
    df_suara = rekap_per_suara(start=start, end=end, jenis=jenis_pilih or None)
except ValueError as exc:
    st.error(f"Filter tidak valid: {exc}")
    st.stop()

if suara_pilih:
    df_suara = df_suara[df_suara["suara"].isin(suara_pilih)]

tabel_anggota = label_per_anggota(df_anggota)
tabel_suara = label_per_suara(df_suara)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Sesi pada periode", int(df_suara["jumlah_sesi"].iloc[0]) if len(df_suara.index) else 0)
kpi2.metric("Anggota tampil", len(df_anggota.index))
kpi3.metric(
    "Rata-rata skor",
    f"{df_anggota['skor'].mean():.2f}" if len(df_anggota.index) else "0.00",
)
kpi4.metric(
    "Tercatat",
    int(df_suara["total_tercatat"].sum()) if len(df_suara.index) else 0,
)

st.caption(f"Periode: {start.isoformat()} s.d. {end.isoformat()} · {CATATAN_SKOR}")

st.divider()
st.subheader("Rekap per Anggota")
st.dataframe(
    tabel_anggota,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Skor": st.column_config.NumberColumn("Skor", format="%.2f"),
        "Predikat": st.column_config.TextColumn("Predikat", width="small"),
    },
)

col_csv, col_xlsx, _ = st.columns([1, 1, 3])
nama_berkas = f"rekap_anggota_{start.isoformat()}_{end.isoformat()}"
col_csv.download_button(
    "⬇️ Unduh CSV (anggota)",
    data=to_csv(tabel_anggota),
    file_name=f"{nama_berkas}.csv",
    mime=CSV_MIME,
    use_container_width=True,
)
col_xlsx.download_button(
    "⬇️ Unduh Excel (anggota)",
    data=to_xlsx(tabel_anggota),
    file_name=f"{nama_berkas}.xlsx",
    mime=XLSX_MIME,
    use_container_width=True,
)

st.divider()
st.subheader("Rekap per Suara")
st.dataframe(
    tabel_suara,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Rata-rata Skor": st.column_config.NumberColumn("Rata-rata Skor", format="%.2f"),
        "Persentase Hadir (%)": st.column_config.NumberColumn(
            "Persentase Hadir (%)", format="%.2f"
        ),
        "Predikat": st.column_config.TextColumn("Predikat", width="small"),
    },
)

col_csv2, col_xlsx2, _ = st.columns([1, 1, 3])
nama_berkas_suara = f"rekap_suara_{start.isoformat()}_{end.isoformat()}"
col_csv2.download_button(
    "⬇️ Unduh CSV (suara)",
    data=to_csv(tabel_suara),
    file_name=f"{nama_berkas_suara}.csv",
    mime=CSV_MIME,
    use_container_width=True,
)
col_xlsx2.download_button(
    "⬇️ Unduh Excel (suara)",
    data=to_xlsx(tabel_suara),
    file_name=f"{nama_berkas_suara}.xlsx",
    mime=XLSX_MIME,
    use_container_width=True,
)

st.caption(
    "Persentase hadir per suara = total Hadir / total baris presensi tercatat. "
    "Rata-rata skor memakai bobot dan ambang dari halaman Pengaturan."
)
