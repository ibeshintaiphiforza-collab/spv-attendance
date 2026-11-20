from __future__ import annotations

import streamlit as st

from core.db import init_db
from core.settings import (
    AMBANG_KEYS,
    BOBOT_KEYS,
    LABEL_AMBANG,
    LABEL_BOBOT,
    default_settings,
    load_settings,
    predikat,
    reset_settings,
    save_settings,
    weighted_score,
)

st.set_page_config(page_title="Pengaturan | Saint Paul Voices", page_icon="⚙️")
init_db()

CONTOH_4_SESI = {"Hadir": 2, "Izin": 1, "Sakit": 0, "Alpa": 1}

st.title("⚙️ Pengaturan Penilaian")
st.caption(
    "Atur bobot kehadiran dan ambang predikat. Nilai bobot 0–1, ambang 0–100."
)

if "form_version" not in st.session_state:
    st.session_state.form_version = 0

aktif = load_settings()
version = st.session_state.form_version

for key in BOBOT_KEYS + AMBANG_KEYS:
    widget_key = f"{key}_{version}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = aktif[key]

st.subheader("Bobot Kehadiran")
bobot_input: dict[str, float] = {}
cols = st.columns(4)
for col, key in zip(cols, BOBOT_KEYS):
    with col:
        bobot_input[key] = st.number_input(
            f"{LABEL_BOBOT[key]} (0–1)",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            format="%.2f",
            key=f"{key}_{version}",
        )

st.subheader("Ambang Predikat")
ambang_input: dict[str, float] = {}
cols = st.columns(3)
for col, key in zip(cols, AMBANG_KEYS):
    with col:
        ambang_input[key] = st.number_input(
            LABEL_AMBANG[key],
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.1f",
            key=f"{key}_{version}",
        )
st.caption("Nilai di bawah ambang C dihitung sebagai predikat D.")

form_values = {**bobot_input, **ambang_input}

st.divider()

col_simpan, col_reset = st.columns([1, 1])
with col_simpan:
    simpan = st.button("💾 Simpan Pengaturan", type="primary", use_container_width=True)
with col_reset:
    reset = st.button("↩️ Reset ke Default", use_container_width=True)

if simpan:
    try:
        aktif = save_settings(form_values)
    except ValueError as exc:
        st.error(f"Pengaturan tidak valid: {exc}")
    else:
        st.session_state.form_version += 1
        st.session_state.flash = ("success", "Pengaturan berhasil disimpan.")
        st.rerun()

if reset:
    aktif = reset_settings()
    st.session_state.form_version += 1
    st.session_state.flash = ("success", "Pengaturan dikembalikan ke nilai default.")
    st.rerun()

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])

st.divider()
st.subheader("Ringkasan Bobot Aktif")
st.dataframe(
    [
        {"Status": LABEL_BOBOT[key], "Bobot": aktif[key]}
        for key in BOBOT_KEYS
    ],
    hide_index=True,
    use_container_width=True,
)
bawaan = default_settings()
st.write(
    f"Ambang predikat: A ≥ {aktif['ambang_a']:g}, B ≥ {aktif['ambang_b']:g}, "
    f"C ≥ {aktif['ambang_c']:g}, di bawahnya D. "
    f"(Default: A {bawaan['ambang_a']:g}, B {bawaan['ambang_b']:g}, "
    f"C {bawaan['ambang_c']:g})"
)

skor = weighted_score(aktif, CONTOH_4_SESI)
st.info(
    f"Contoh 4 sesi (2 Hadir, 1 Izin, 1 Alpa) → skor **{skor:g}** → "
    f"predikat **{predikat(skor, aktif)}**."
)
