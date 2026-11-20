from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core.anggota import list_anggota
from core.db import init_db
from core.penilaian import jumlah_tercatat, rekap_per_anggota
from core.presensi import STATUS_VALID, list_sesi, ringkasan_sesi, teks_ringkasan, total_dicatat

st.set_page_config(page_title="Dashboard | Saint Paul Voices", page_icon="🏠", layout="wide")
init_db()

HARI_PERIODE = 30

hari_ini = date.today()
awal_periode = hari_ini - timedelta(days=HARI_PERIODE - 1)

st.title("🏠 Dashboard Presensi")
st.caption(
    f"Ringkasan {HARI_PERIODE} hari terakhir "
    f"({awal_periode.isoformat()} s.d. {hari_ini.isoformat()})."
)

jumlah_anggota = len(list_anggota(aktif_only=True))
sesi_periode = list_sesi(start=awal_periode, end=hari_ini)
sesi_terbaru = list_sesi()[:5]
rekap = rekap_per_anggota(start=awal_periode, end=hari_ini)
tercatat = jumlah_tercatat(start=awal_periode, end=hari_ini)

total_tercatat = sum(tercatat.values())
persen_hadir = tercatat["Hadir"] / total_tercatat * 100 if total_tercatat else 0.0
berdata = rekap.loc[rekap["jumlah_sesi"] > 0, "skor"] if len(rekap.index) else pd.Series(dtype=float)
rata_skor = float(berdata.mean()) if len(berdata.index) else 0.0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Anggota aktif", jumlah_anggota)
kpi2.metric(f"Sesi {HARI_PERIODE} hari", len(sesi_periode))
kpi3.metric("Rata-rata skor", f"{rata_skor:.2f}" if len(berdata.index) else "—")
kpi4.metric("Kehadiran", f"{persen_hadir:.1f}%" if total_tercatat else "—")

if not sesi_periode:
    st.info("Belum ada sesi pada periode ini. Tambahkan sesi di halaman Presensi.")

st.divider()
st.subheader("Tren Kehadiran per Sesi")
if sesi_periode:
    # sesi_periode terurut terbaru dulu; dibalik agar grafik berjalan kronologis.
    tren = []
    for sesi in reversed(sesi_periode):
        hitung = ringkasan_sesi(sesi["id"])
        jumlah = total_dicatat(hitung)
        tren.append(
            {
                "Tanggal": sesi["tanggal"],
                "Persen Hadir (%)": round(hitung["Hadir"] / jumlah * 100, 1) if jumlah else 0.0,
            }
        )
    st.bar_chart(pd.DataFrame(tren).set_index("Tanggal")["Persen Hadir (%)"])
else:
    st.caption("Grafik muncul setelah ada sesi dan presensi pada periode ini.")

st.subheader("Komposisi Status Presensi (periode)")
if total_tercatat:
    st.bar_chart(
        pd.DataFrame(
            {"Jumlah": [tercatat[status] for status in STATUS_VALID]},
            index=pd.Index(STATUS_VALID, name="Status"),
        )["Jumlah"]
    )
    st.caption(f"Total baris presensi tercatat: {total_tercatat}.")
else:
    st.caption("Belum ada presensi tercatat pada periode ini.")

st.divider()
st.subheader("5 Sesi Terbaru")
if sesi_terbaru:
    st.dataframe(
        [
            {
                "Tanggal": sesi["tanggal"],
                "Jenis": sesi["jenis"],
                "Pencatatan": teks_ringkasan(ringkasan_sesi(sesi["id"])),
                "Catatan": sesi["catatan"] or "",
            }
            for sesi in sesi_terbaru
        ],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.caption("Belum ada sesi yang tercatat.")
