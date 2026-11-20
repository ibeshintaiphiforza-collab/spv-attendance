from __future__ import annotations

import streamlit as st

from core.db import init_db

st.set_page_config(
    page_title="Presensi Saint Paul Voices",
    page_icon="🎵",
    layout="wide",
)

init_db()

halaman = st.navigation(
    [
        st.Page("pages/1_Dashboard.py", title="Dashboard", icon="🏠", url_path="dashboard", default=True),
        st.Page("pages/2_Anggota.py", title="Anggota", icon="👥", url_path="anggota"),
        st.Page("pages/3_Presensi.py", title="Presensi", icon="✅", url_path="presensi"),
        st.Page("pages/4_Rekap.py", title="Rekap", icon="📊", url_path="rekap"),
        st.Page("pages/5_Pengaturan.py", title="Pengaturan", icon="⚙️", url_path="pengaturan"),
    ],
    position="sidebar",
)

st.sidebar.title("Saint Paul Voices")
st.sidebar.caption(
    "Aplikasi presensi paduan suara: anggota, kehadiran, rekap, dan penilaian."
)

halaman.run()
