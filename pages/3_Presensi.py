from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.db import init_db
from core.presensi import (
    JENIS_VALID,
    STATUS_DEFAULT,
    STATUS_VALID,
    PresensiError,
    anggota_aktif,
    get_atau_buat_sesi,
    hapus_sesi,
    list_sesi,
    muat_presensi,
    ringkasan_sesi,
    simpan_presensi,
    teks_ringkasan,
    total_dicatat,
)

st.set_page_config(page_title="Presensi | Saint Paul Voices", page_icon="📋", layout="wide")
init_db()

EDITOR_KEY = "editor_presensi"

st.title("📋 Presensi Paduan Suara")
st.caption("Catat kehadiran anggota per sesi latihan, misa, atau tampil.")

col_tanggal, col_jenis = st.columns([1.2, 1])
with col_tanggal:
    tanggal = st.date_input("Tanggal", value=date.today(), format="YYYY-MM-DD")
with col_jenis:
    jenis = st.selectbox("Jenis sesi", list(JENIS_VALID))

sesi = next(
    (
        s
        for s in list_sesi(start=tanggal, end=tanggal, jenis=jenis)
        if s["tanggal"] == tanggal.isoformat()
    ),
    None,
)
sesi_id = sesi["id"] if sesi else None
catatan_lama = (sesi or {}).get("catatan") or ""
tersimpan = muat_presensi(sesi_id) if sesi_id else {}

kunci_konteks = f"{tanggal.isoformat()}|{jenis}|{sesi_id}"
if st.session_state.get("konteks_presensi") != kunci_konteks:
    # Pindah tanggal/jenis: editor baru memuat nilai tersimpan (default Hadir).
    st.session_state["konteks_presensi"] = kunci_konteks
    st.session_state["versi_editor"] = st.session_state.get("versi_editor", 0) + 1
    st.session_state["catatan_presensi"] = catatan_lama

if sesi_id:
    st.caption(
        f"Sesi tersimpan: {tanggal.isoformat()} · {jenis} — "
        f"{teks_ringkasan(ringkasan_sesi(sesi_id))}"
    )
else:
    st.caption("Sesi ini belum ada di database; sesi dibuat saat presensi disimpan.")

daftar = anggota_aktif()

DS_EDITOR = {
    "nis": st.column_config.TextColumn("NIS", disabled=True, width="small"),
    "nama": st.column_config.TextColumn("Nama", disabled=True),
    "suara": st.column_config.TextColumn("Suara", disabled=True, width="small"),
    "status": st.column_config.SelectboxColumn(
        "Status", options=list(STATUS_VALID), required=True, width="small"
    ),
}

if not daftar:
    st.info(
        "Belum ada anggota aktif. Tambahkan anggota terlebih dahulu di halaman Data Anggota."
    )
else:
    st.subheader("Kehadiran Anggota")
    versi = st.session_state.setdefault("versi_editor", 0)
    editor_key = f"{EDITOR_KEY}_{versi}"
    col_a, col_b, _spacer = st.columns([1, 1, 3])
    if col_a.button("✅ Semua Hadir", use_container_width=True):
        st.session_state["prefill_presensi"] = "Hadir"
        st.session_state["versi_editor"] = versi + 1
        st.rerun()
    if col_b.button("↩️ Reset", use_container_width=True):
        st.session_state.pop("prefill_presensi", None)
        st.session_state["versi_editor"] = versi + 1
        st.session_state["catatan_presensi"] = catatan_lama
        st.rerun()

    prefill = st.session_state.pop("prefill_presensi", None)
    df = pd.DataFrame(
        [
            {
                "nis": a["nis"],
                "nama": a["nama"],
                "suara": a["suara"],
                "status": prefill or tersimpan.get(a["id"], STATUS_DEFAULT),
            }
            for a in daftar
        ]
    )
    hasil = st.data_editor(
        df,
        key=editor_key,
        hide_index=True,
        use_container_width=True,
        disabled=["nis", "nama", "suara"],
        column_config=DS_EDITOR,
    )

    catatan_final = st.text_input(
        "Catatan sesi (opsional, disimpan bersama presensi)",
        key="catatan_presensi",
        placeholder="mis. Latihan rutin Jumat",
    )

    if st.button("💾 Simpan presensi", type="primary"):
        status_map = {
            a["id"]: hasil.iloc[posisi]["status"]
            for posisi, a in enumerate(daftar)
            if posisi < len(hasil)
        }
        try:
            sesi_id = get_atau_buat_sesi(
                tanggal, jenis, catatan_final.strip() or None
            )
            ringkasan = simpan_presensi(sesi_id, status_map, catatan=catatan_final)
        except PresensiError as exc:
            st.error(f"Presensi tidak disimpan: {exc}")
        else:
            st.session_state["konteks_presensi"] = None
            st.session_state["versi_editor"] = versi + 1
            st.session_state.flash = (
                "success",
                f"Presensi {tanggal.isoformat()} · {jenis} tersimpan — "
                f"{teks_ringkasan(ringkasan)} (total {total_dicatat(ringkasan)} anggota).",
            )
            st.rerun()

# ---------------------------------------------------------------- Sesi terbaru
st.divider()
st.subheader("10 Sesi Terbaru")
terbaru = list_sesi()[:10]
if not terbaru:
    st.info("Belum ada sesi presensi yang tersimpan.")
else:
    baris_sesi = []
    for s in terbaru:
        r = ringkasan_sesi(s["id"])
        baris_sesi.append(
            {
                "ID": s["id"],
                "Tanggal": s["tanggal"],
                "Jenis": s["jenis"],
                "Hadir": r["Hadir"],
                "Izin": r["Izin"],
                "Sakit": r["Sakit"],
                "Alpa": r["Alpa"],
                "Total": total_dicatat(r),
                "Catatan": s["catatan"] or "",
            }
        )
    st.dataframe(pd.DataFrame(baris_sesi), hide_index=True, use_container_width=True)

    label_sesi = {
        s["id"]: f"{s['tanggal']} · {s['jenis']}" for s in terbaru
    }
    with st.expander("🗑️ Hapus sesi"):
        pilihan = st.selectbox(
            "Pilih sesi",
            list(label_sesi),
            format_func=lambda i: label_sesi[i],
            key="pilih_hapus_sesi",
        )
        konfirmasi = st.checkbox(
            f"Yakin menghapus sesi {label_sesi[pilihan]} beserta seluruh presensinya?",
            key="konfirmasi_hapus_sesi",
        )
        if st.button("Hapus sesi", disabled=not konfirmasi, key="hapus_sesi"):
            hapus_sesi(pilihan)
            st.session_state["konteks_presensi"] = None
            st.session_state["versi_editor"] = st.session_state.get("versi_editor", 0) + 1
            st.session_state.flash = ("success", f"Sesi {label_sesi[pilihan]} dihapus.")
            st.rerun()

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
