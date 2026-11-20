from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core.anggota import (
    SUARA_VALID,
    AnggotaError,
    edit_anggota,
    hapus_anggota,
    import_anggota,
    list_anggota,
    set_aktif,
    tambah_anggota,
)
from core.db import init_db

st.set_page_config(page_title="Anggota | Saint Paul Voices", page_icon="👥", layout="wide")
init_db()

KOLOM_TEMPLATE = ["NIS", "Nama", "Kelas", "Suara"]
KOLOM_WAJIB = ["NIS", "Nama", "Kelas"]


def _baca_berkas(berkas) -> pd.DataFrame:
    """Baca CSV (pemisah , atau ;) atau Excel menjadi DataFrame teks."""
    nama = (berkas.name or "").lower()
    raw = berkas.getvalue() if hasattr(berkas, "getvalue") else berkas.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if nama.endswith((".xlsx", ".xls")):
        try:
            return pd.read_excel(io.BytesIO(raw), dtype=str, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001 - pesan ramah untuk file rusak
            raise ValueError(f"File Excel tidak bisa dibaca: {exc}") from exc
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            teks = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 menerima semua byte
        raise ValueError("Encoding berkas tidak dikenali.")
    try:
        return pd.read_csv(
            io.StringIO(teks), sep=None, engine="python", dtype=str, skipinitialspace=True
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"File CSV tidak bisa dibaca: {exc}") from exc


def _validasi_kolom(df: pd.DataFrame) -> list[str]:
    ada = {str(kolom).strip().lower() for kolom in df.columns}
    return [kolom for kolom in KOLOM_WAJIB if kolom.lower() not in ada]


st.title("👥 Data Anggota Paduan Suara")
st.caption(
    "Kelola daftar anggota, status aktif, dan import massal dari file CSV/Excel."
)

# ---------------------------------------------------------------- Daftar
st.subheader("Daftar Anggota")
col_filter, col_nonaktif = st.columns([2, 1])
with col_filter:
    filter_suara = st.selectbox(
        "Filter suara", ["Semua"] + list(SUARA_VALID), key="filter_suara"
    )
with col_nonaktif:
    tampil_nonaktif = st.toggle("Tampilkan anggota nonaktif", value=True)

semua = list_anggota(suara=None if filter_suara == "Semua" else filter_suara)
tampil = semua if tampil_nonaktif else [a for a in semua if a["aktif"]]

if tampil:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "ID": a["id"],
                    "NIS": a["nis"],
                    "Nama": a["nama"],
                    "Kelas": a["kelas"] or "",
                    "Suara": a["suara"],
                    "Status": "Aktif" if a["aktif"] else "Nonaktif",
                }
                for a in tampil
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"{len(tampil)} dari {len(semua)} anggota ditampilkan.")
else:
    st.info("Belum ada anggota yang cocok dengan filter tersebut.")

# ---------------------------------------------------------------- Ubah status
st.subheader("Aktifkan / Nonaktifkan Anggota")
if semua:
    label_anggota = {
        a["id"]: f"{a['nama']} ({a['nis']}) — {a['suara']}"
        + ("" if a["aktif"] else " [nonaktif]")
        for a in semua
    }
    pilihan_status = st.selectbox(
        "Pilih anggota",
        list(label_anggota),
        format_func=lambda i: label_anggota[i],
        key="pilih_status",
    )
    target = next(a for a in semua if a["id"] == pilihan_status)
    col_on, col_off = st.columns(2)
    with col_on:
        if st.button(
            "✅ Aktifkan", disabled=target["aktif"], use_container_width=True
        ):
            set_aktif(pilihan_status, True)
            st.session_state.flash = ("success", "Anggota diaktifkan kembali.")
            st.rerun()
    with col_off:
        if st.button(
            "🚫 Nonaktifkan", disabled=not target["aktif"], use_container_width=True
        ):
            set_aktif(pilihan_status, False)
            st.session_state.flash = ("success", "Anggota dinonaktifkan.")
            st.rerun()
else:
    st.caption("Belum ada anggota untuk diubah statusnya.")

# ---------------------------------------------------------------- Form
with st.expander("➕ Tambah Anggota", expanded=not semua):
    with st.form("form_tambah_anggota", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        nis_baru = col1.text_input("NIS *")
        nama_baru = col2.text_input("Nama *")
        kelas_baru = col3.text_input("Kelas")
        suara_baru = col4.selectbox("Suara *", list(SUARA_VALID))
        simpan_baru = st.form_submit_button("Simpan Anggota", type="primary")
    if simpan_baru:
        try:
            tambah_anggota(nis_baru, nama_baru, kelas_baru, suara_baru)
        except AnggotaError as exc:
            st.error(f"Gagal menyimpan: {exc}")
        else:
            st.session_state.flash = (
                "success",
                f"Anggota {nama_baru.strip()} berhasil ditambahkan.",
            )
            st.rerun()

with st.expander("✏️ Edit Anggota"):
    if not semua:
        st.caption("Belum ada anggota yang bisa diedit.")
    else:
        label_edit = {
            a["id"]: f"{a['nama']} ({a['nis']}) — {a['suara']}" for a in semua
        }
        pilihan_edit = st.selectbox(
            "Pilih anggota yang diedit",
            list(label_edit),
            format_func=lambda i: label_edit[i],
            key="pilih_edit",
        )
        data_edit = next(a for a in semua if a["id"] == pilihan_edit)
        versi = st.session_state.setdefault("versi_edit", {})
        versi.setdefault("id", None)
        if versi["id"] != pilihan_edit:
            versi["id"] = pilihan_edit
            versi["n"] = versi.get("n", 0) + 1
        v = f"_{versi['n']}"
        with st.form("form_edit_anggota"):
            col1, col2, col3, col4 = st.columns(4)
            nis_edit = col1.text_input("NIS *", value=data_edit["nis"], key="edit_nis" + v)
            nama_edit = col2.text_input(
                "Nama *", value=data_edit["nama"], key="edit_nama" + v
            )
            kelas_edit = col3.text_input(
                "Kelas", value=data_edit["kelas"] or "", key="edit_kelas" + v
            )
            suara_edit = col4.selectbox(
                "Suara *",
                list(SUARA_VALID),
                index=list(SUARA_VALID).index(data_edit["suara"]),
                key="edit_suara" + v,
            )
            simpan_edit = st.form_submit_button("Simpan Perubahan", type="primary")
        if simpan_edit:
            try:
                edit_anggota(pilihan_edit, nis_edit, nama_edit, kelas_edit, suara_edit)
            except AnggotaError as exc:
                st.error(f"Gagal menyimpan perubahan: {exc}")
            else:
                st.session_state.flash = ("success", "Perubahan anggota tersimpan.")
                st.rerun()

with st.expander("🗑️ Hapus Anggota"):
    if not semua:
        st.caption("Belum ada anggota yang bisa dihapus.")
    else:
        label_hapus = {
            a["id"]: f"{a['nama']} ({a['nis']}) — {a['suara']}" for a in semua
        }
        pilihan_hapus = st.selectbox(
            "Pilih anggota",
            list(label_hapus),
            format_func=lambda i: label_hapus[i],
            key="pilih_hapus",
        )
        st.caption(
            "Anggota yang sudah memiliki riwayat presensi hanya akan dinonaktifkan "
            "agar data kehadiran tetap utuh."
        )
        if st.button("Hapus", key="hapus_anggota"):
            try:
                aksi = hapus_anggota(pilihan_hapus)
            except AnggotaError as exc:
                st.error(str(exc))
            else:
                st.session_state.flash = ("success", f"Anggota {aksi}.")
                st.rerun()

# ---------------------------------------------------------------- Import
st.divider()
st.subheader("📥 Import Anggota")
st.caption(
    "Kolom wajib: NIS, Nama, Kelas. Kolom opsional: Suara, Aktif. "
    "NIS yang sudah ada akan diperbarui, NIS baru akan ditambahkan."
)

template = pd.DataFrame(
    [
        {"NIS": "2024001", "Nama": "Maria Contoh", "Kelas": "XI IPA 1", "Suara": "Sopran"},
        {"NIS": "2024002", "Nama": "Yohanes Contoh", "Kelas": "X IPS 2", "Suara": "Tenor"},
    ]
)
st.download_button(
    "⬇️ Unduh Template CSV",
    data=template.to_csv(index=False),
    file_name="template_anggota.csv",
    mime="text/csv",
)

berkas = st.file_uploader(
    "Unggah file anggota", type=["csv", "xlsx", "xls"], key="unggah_anggota"
)

if berkas is not None:
    tag_berkas = f"{berkas.name}:{berkas.size}"
    try:
        df_unggah = _baca_berkas(berkas)
    except ValueError as exc:
        st.error(str(exc))
    else:
        df_unggah = df_unggah.dropna(how="all")
        kurang = _validasi_kolom(df_unggah)
        if kurang:
            st.error(
                "Kolom berikut tidak ditemukan di file: "
                f"{', '.join(kurang)}. Periksa header file atau unduh template."
            )
        else:
            st.write(f"**Pratinjau {len(df_unggah)} baris** — {berkas.name}")
            st.dataframe(df_unggah.head(200), hide_index=True, use_container_width=True)
            if len(df_unggah) > 200:
                st.caption("Pratinjau hanya menampilkan 200 baris pertama.")

            pakai_default = (
                "Suara" not in {str(k).strip().lower() for k in df_unggah.columns}
            )
            suara_default = None
            if pakai_default:
                suara_default = st.selectbox(
                    "Suara default untuk baris tanpa kolom Suara",
                    list(SUARA_VALID),
                    key="suara_default_import",
                )
                st.caption(
                    "File tidak memiliki kolom Suara, suara default di atas akan dipakai."
                )

            konfirmasi = st.checkbox(
                "Saya sudah memeriksa pratinjau dan ingin menyimpan data ini.",
                key=f"konfirmasi_{tag_berkas}",
            )
            if st.button("Import", type="primary", disabled=not konfirmasi):
                try:
                    ringkasan = import_anggota(df_unggah, default_suara=suara_default)
                except AnggotaError as exc:
                    st.error(f"Import dibatalkan: {exc}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Terjadi kesalahan saat import, tidak ada data disimpan: {exc}")
                else:
                    jumlah_gagal = len(ringkasan["gagal"])
                    if ringkasan["total"] and jumlah_gagal:
                        st.warning(ringkasan["pesan"])
                    elif ringkasan["total"]:
                        st.success(ringkasan["pesan"])
                    else:
                        st.error(ringkasan["pesan"])
                    st.write(
                        f"Ditambahkan: **{ringkasan['ditambah']}** · "
                        f"Diperbarui: **{ringkasan['diperbarui']}** · "
                        f"Gagal/dilewati: **{jumlah_gagal}**"
                    )
                    if ringkasan["gagal"]:
                        st.dataframe(
                            pd.DataFrame(ringkasan["gagal"]).rename(
                                columns={"baris": "Baris", "nis": "NIS", "alasan": "Alasan"}
                            ),
                            hide_index=True,
                            use_container_width=True,
                        )

flash = st.session_state.pop("flash", None)
if flash:
    getattr(st, flash[0])(flash[1])
