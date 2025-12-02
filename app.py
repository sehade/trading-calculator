import streamlit as st
import pandas as pd
from datetime import datetime
import io
import uuid # Untuk ID unik setiap trade

# ==========================================
# 1. KONFIGURASI TAMPILAN & CSS
# ==========================================
st.set_page_config(
    page_title="Pro Trading Journal (CRUD)",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Modern
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    
    /* Style Kartu Statistik */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
    }
    
    /* Tombol Tambah (Hijau) */
    div.stButton > button:first-child {
        background-color: #00CC96;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem;
        width: 100%;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #00a87d;
        transform: scale(1.02);
    }
    
    /* Font Custom */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SEMENTARA (SESSION STATE)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. ENGINE PERHITUNGAN (BACKEND)
# ==========================================
def calculate_trade(coin, status, margin_mode, total_equity, pos_type, margin, lev, entry, tp, sl, fee_pct, fund_rate, days):
    # Validasi input untuk mencegah error pembagian 0
    if entry <= 0: return None 
    
    # 1. Hitung Size
    pos_size = margin * lev
    qty = pos_size / entry
    
    # 2. Hitung Fee
    trade_fee = pos_size * (fee_pct / 100)
    fund_fee = pos_size * (fund_rate / 100) * days
    total_fee = trade_fee + fund_fee
    
    # 3. Hitung Likuidasi (Jantung Logika)
    if margin_mode == "Isolated Margin":
        risk_capital = margin
    else: 
        # Cross: Menggunakan Total Equity dikurangi Fee
        risk_capital = total_equity - total_fee 
        
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, entry - buffer)
        gross_pnl_tp = (tp - entry) * qty
        gross_pnl_sl = (sl - entry) * qty if sl > 0 else -risk_capital
    else: # Short
        liq_price = entry + buffer
        gross_pnl_tp = (entry - tp) * qty
        gross_pnl_sl = (entry - sl) * qty if sl > 0 else -risk_capital

    # 4. Net Results
    net_profit_tp = gross_pnl_tp - total_fee
    net_loss_sl = gross_pnl_sl - total_fee
    
    # RETURN DICTIONARY (Struktur Data Baris)
    return {
        "ID": str(uuid.uuid4()), # ID Baru jika create
        "Waktu": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Pair/Coin": coin.upper(),
        "Status": status,
        "Arah": pos_type,
        "Mode": margin_mode,
        "Margin ($)": float(margin),
        "Lev (x)": int(lev),
        "Entry": float(entry),
        "TP": float(tp),
        "SL": float(sl),
        "Liq Price": float(liq_price),
        "Fee Total ($)": float(total_fee),
        "Est. Profit ($)": float(net_profit_tp),
        "Est. Loss ($)": float(net_loss_sl)
    }

# ==========================================
# 4. SIDEBAR (CREATE INPUT)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Jurnal")
    
    # A. Global Settings
    st.caption("--- 1. Info Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # B. Identitas Trade
    st.caption("--- 2. Identitas Trade ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    trade_status = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])

    # C. Setup Posisi
    st.caption("--- 3. Setup Posisi ---")
    pos_type = st.radio("Arah", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True, label_visibility="collapsed")
    c1, c2 = st.columns(2)
    with c1: margin_input = st.number_input("Margin ($)", value=10.0, min_value=1.0)
    with c2: lev_input = st.number_input("Leverage (x)", value=20, min_value=1)

    # D. Harga
    st.caption("--- 4. Harga ---")
    entry_input = st.number_input("Entry Price", value=50000.0, format="%.6f")
    c3, c4 = st.columns(2)
    with c3: tp_input = st.number_input("Target (TP)", value=55000.0, format="%.6f")
    with c4: sl_input = st.number_input("Stop Loss (SL)", value=48000.0, format="%.6f")

    # E. Fee Settings (Global untuk Input Baru)
    with st.expander("⚙️ Fee Settings"):
        fee_pct = st.number_input("Fee (%)", value=0.045, format="%.4f")
        fund_rate = st.number_input("Funding (%)", value=0.010, format="%.3f")
        days_hold = st.number_input("Hari", value=0)

    st.markdown("---")
    
    # TOMBOL CREATE
    if st.button("➕ Tambah Data"):
        if entry_input > 0:
            res = calculate_trade(coin_name, trade_status, margin_mode, total_equity, pos_type, margin_input, lev_input, entry_input, tp_input, sl_input, fee_pct, fund_rate, days_hold)
            if res:
                st.session_state['portfolio'].append(res)
                st.toast("Data berhasil ditambahkan!", icon="✅")
        else:
            st.error("Entry Price wajib diisi!")

# ==========================================
# 5. DASHBOARD UTAMA (READ, UPDATE, DELETE)
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.title("💎 Pro Trading Journal")
    st.caption(f"Saldo Aset: **${total_equity:,.2f}** | Kelola data Anda langsung pada tabel di bawah.")
with c_head2:
    st.metric("Mode Aktif", margin_mode)

st.markdown("---")

# Cek apakah database kosong
if len(st.session_state['portfolio']) > 0:
    
    # Persiapan DataFrame
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # --- A. TABEL CRUD INTERAKTIF ---
    st.subheader("📋 Manajemen Data (Edit & Hapus)")
    st.info("💡 **Tips:** Klik angka di tabel untuk mengedit. Centang kotak di kiri baris lalu tekan 'Delete' untuk menghapus. Perhitungan akan otomatis diupdate.")

    # Konfigurasi Kolom (Mana yang bisa diedit, mana yang dikunci)
    column_config = {
        "ID": None, # Sembunyikan ID (Internal use only)
        "Status": st.column_config.SelectboxColumn(
            "Status", options=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], width="medium", required=True
        ),
        "Arah": st.column_config.SelectboxColumn(
            "Arah", options=["Long (Buy) 🟢", "Short (Sell) 🔴"], width="small", required=True
        ),
        "Mode": st.column_config.SelectboxColumn(
            "Mode", options=["Isolated Margin", "Cross Margin"], width="small"
        ),
        "Margin ($)": st.column_config.NumberColumn("Margin", format="$%.2f", min_value=0),
        "Entry": st.column_config.NumberColumn("Entry", format="%.4f", min_value=0.000001),
        "TP": st.column_config.NumberColumn("TP", format="%.4f"),
        "SL": st.column_config.NumberColumn("SL", format="%.4f"),
        
        # Kolom Hasil (Dikunci/Disabled agar user tidak asal tulis)
        "Liq Price": st.column_config.NumberColumn("Liq Price", format="%.4f", disabled=True),
        "Fee Total ($)": st.column_config.NumberColumn("Fee", format="$%.2f", disabled=True),
        "Est. Profit ($)": st.column_config.NumberColumn("Profit", format="$%.2f", disabled=True),
        "Est. Loss ($)": st.column_config.NumberColumn("Loss", format="$%.2f", disabled=True),
    }

    # RENDER TABEL EDITOR
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        num_rows="dynamic", # Mengizinkan Delete & Add row
        use_container_width=True,
        hide_index=True,
        key="editor"
    )

    # --- B. LOGIKA SINKRONISASI CERDAS (100% VALIDATION FIX) ---
    # Jika tabel diedit, kita hitung ulang matematikanya
    if not edited_df.equals(df):
        
        updated_data = edited_df.to_dict('records')
        recalculated_portfolio = []
        
        for row in updated_data:
            # Kita panggil fungsi calculate_trade lagi untuk update Profit/Liq/Fee
            # berdasarkan angka baru yang diinput user di tabel
            
            # Catatan: Kita gunakan fee setting global dari sidebar untuk re-kalkulasi
            # (Simplifikasi agar user tidak perlu edit fee per row)
            recalc = calculate_trade(
                coin=row.get("Pair/Coin"),
                status=row.get("Status"),
                margin_mode=row.get("Mode"),
                total_equity=total_equity, # Menggunakan Equity Global terkini
                pos_type=row.get("Arah"),
                margin=row.get("Margin ($)"),
                lev=row.get("Lev (x)"),
                entry=row.get("Entry"),
                tp=row.get("TP"),
                sl=row.get("SL"),
                fee_pct=fee_pct, 
                fund_rate=fund_rate, 
                days=days_hold
            )
            
            if recalc:
                # Pertahankan ID dan Waktu lama agar tidak jadi trade baru
                recalc["ID"] = row.get("ID")
                recalc["Waktu"] = row.get("Waktu")
                recalculated_portfolio.append(recalc)
        
        # Simpan hasil update ke session state & refresh
        st.session_state['portfolio'] = recalculated_portfolio
        st.rerun()

    # --- C. STATISTIK REAL-TIME ---
    st.markdown("---")
    st.subheader("📈 Statistik Portfolio")
    
    total_margin = edited_df['Margin ($)'].sum()
    total_profit = edited_df['Est. Profit ($)'].sum()
    usage_pct = (total_margin / total_equity) * 100
    
    # Health Bar
    if usage_pct < 5: color, status = "#00CC96", "AMAN"
    elif usage_pct < 20: color, status = "#FFAA00", "WARNING"
    else: color, status = "#FF4B4B", "BAHAYA"
    
    st.markdown(f"""
        <div style="background-color: #262730; border-radius: 5px; margin-bottom: 5px;">
            <div style="width: {min(usage_pct, 100)}%; background-color: {color}; height: 20px; border-radius: 5px;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #aaa;">
            <span>Margin: <b>${total_margin:,.2f}</b></span>
            <span>Status: <b style="color:{color}">{status}</b></span>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total Trade", len(edited_df))
    with c2: st.metric("Total Equity", f"${total_equity:,.2f}")
    with c3: st.metric("Total Potensi Cuan", f"${total_profit:,.2f}")

    # --- D. EXPORT EXCEL ---
    st.markdown("### 📥 Download Laporan")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='Jurnal')
        
    st.download_button(
        label="Download Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"Jurnal_Trading_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👋 Database kosong. Silakan input trade baru di Sidebar.")
