import streamlit as st
import pandas as pd
from datetime import datetime
import io

# ==========================================
# 1. KONFIGURASI TAMPILAN & CSS
# ==========================================
st.set_page_config(
    page_title="Pro Trading Journal V2",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk tampilan "Dark Mode Professional"
st.markdown("""
<style>
    /* Background Utama */
    .main { background-color: #0e1117; }
    
    /* Kartu Statistik (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Tombol Tambah (Hijau Neon) */
    div.stButton > button:first-child {
        background-color: #00CC96;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        padding: 0.6rem;
        width: 100%;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #00a87d;
        transform: scale(1.02);
    }
    
    /* Progress Bar Custom */
    .stProgress > div > div > div > div {
        background-color: #00CC96;
    }
    
    /* Font Judul */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SEMENTARA (SESSION STATE)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. MESIN PERHITUNGAN (BACKEND LOGIC)
# ==========================================
def calculate_trade(coin, status, margin_mode, total_equity, pos_type, margin, lev, entry, tp, sl, fee_pct, fund_rate, days):
    # --- A. Hitung Dasar ---
    pos_size = margin * lev
    qty = pos_size / entry
    
    # --- B. Hitung Biaya (Fee) ---
    # Trading Fee (Dibayar saat Close) + Funding Fee (Biaya Inap)
    trade_fee = pos_size * (fee_pct / 100)
    fund_fee = pos_size * (fund_rate / 100) * days
    total_fee = trade_fee + fund_fee
    
    # --- C. Logika Likuidasi (Jantung Aplikasi) ---
    if margin_mode == "Isolated Margin":
        # Iso: Hanya Margin yang dipertaruhkan
        risk_capital = margin
    else: 
        # Cross: Total Saldo Aset yang dipertaruhkan (dikurangi fee estimasi)
        risk_capital = total_equity - total_fee 
        
    buffer = risk_capital / qty # Jarak harga toleransi
    
    if "Long" in pos_type:
        liq_price = max(0, entry - buffer)
        # PnL Gross (Belum potong fee)
        gross_pnl_tp = (tp - entry) * qty
        gross_pnl_sl = (sl - entry) * qty if sl > 0 else -risk_capital
    else: # Short
        liq_price = entry + buffer
        gross_pnl_tp = (entry - tp) * qty
        gross_pnl_sl = (entry - sl) * qty if sl > 0 else -risk_capital

    # --- D. PnL Bersih (Net) ---
    net_profit_tp = gross_pnl_tp - total_fee
    net_loss_sl = gross_pnl_sl - total_fee
    
    # Return Data Dictionary (Format Baris Excel)
    return {
        "Waktu Input": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Pair/Coin": coin.upper(),
        "Status": status,
        "Arah": pos_type,
        "Mode": margin_mode,
        "Margin ($)": margin,
        "Lev (x)": lev,
        "Entry": entry,
        "TP": tp,
        "SL": sl,
        "Liq Price": liq_price,
        "Fee Total ($)": total_fee,
        "Est. Profit ($)": net_profit_tp,
        "Est. Loss/Risk ($)": net_loss_sl
    }

# ==========================================
# 4. SIDEBAR (PANEL INPUT)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Jurnal")
    
    # 1. INFO AKUN
    st.caption("--- 1. Info Dompet & Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # 2. IDENTITAS TRADE (FITUR BARU)
    st.caption("--- 2. Identitas Trade ---")
    coin_name = st.text_input("Nama Coin / Pair", value="BTC/USDT", placeholder="Contoh: PEPE, SOL")
    trade_status = st.selectbox(
        "Status Trade", 
        ["🟢 Running (Open)", "🚀 Hit TP (Floating)", "⚠️ Hit SL (Floating)", "🏁 Closed (Selesai)"],
        help="Pilih status saat ini untuk pencatatan."
    )

    # 3. SETUP POSISI
    st.caption("--- 3. Setup Posisi ---")
    pos_type = st.radio("Arah Market", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True, label_visibility="collapsed")
    
    c1, c2 = st.columns(2)
    with c1: margin_input = st.number_input("Margin ($)", value=10.0, min_value=1.0)
    with c2: lev_input = st.number_input("Leverage (x)", value=20, min_value=1, max_value=250)

    # 4. HARGA
    st.caption("--- 4. Titik Harga ---")
    entry_input = st.number_input("Entry Price", value=50000.0, format="%.6f")
    c3, c4 = st.columns(2)
    with c3: tp_input = st.number_input("Target (TP)", value=55000.0, format="%.6f")
    with c4: sl_input = st.number_input("Stop Loss (SL)", value=48000.0, format="%.6f", help="0 = Tanpa SL")

    # 5. BIAYA
    with st.expander("⚙️ Atur Fee & Funding"):
        fee_pct = st.number_input("Fee Trading (%)", value=0.045, step=0.001, format="%.4f")
        fund_rate = st.number_input("Funding Rate/Hari (%)", value=0.010, step=0.001, format="%.3f")
        days_hold = st.number_input("Estimasi Hold (Hari)", value=0, min_value=0)

    # TOMBOL EKSEKUSI
    st.markdown("---")
    if st.button("➕ Tambah ke Portfolio"):
        if entry_input > 0:
            # Panggil fungsi hitung
            res = calculate_trade(coin_name, trade_status, margin_mode, total_equity, pos_type, margin_input, lev_input, entry_input, tp_input, sl_input, fee_pct, fund_rate, days_hold)
            # Simpan ke session state
            st.session_state['portfolio'].append(res)
            st.toast(f"Sukses! {coin_name} ditambahkan.", icon="✅")
        else:
            st.error("Harga Entry tidak boleh 0!")

    if st.button("🗑️ Reset Jurnal"):
        st.session_state['portfolio'] = []
        st.rerun()

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================

# Header
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.title("🚀 Pro Trader Journal")
    st.caption(f"Saldo Aset: **${total_equity:,.2f}** | Mode: **{margin_mode}**")
with c_head2:
    st.metric("Jam Server", datetime.now().strftime("%H:%M"))

st.markdown("---")

# --- BAGIAN A: ANALISIS REAL-TIME (PREVIEW) ---
st.subheader("🔍 Analisis Live (Preview)")
st.info("Angka di bawah ini berubah sesuai input yang Anda ketik di Sidebar.")

# Hitung preview tanpa simpan
preview = calculate_trade(coin_name, trade_status, margin_mode, total_equity, pos_type, margin_input, lev_input, entry_input, tp_input, sl_input, fee_pct, fund_rate, days_hold)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Modal (Margin)", f"${preview['Margin ($)']:,.2f}", f"{lev_input}x Lev")
with m2:
    st.metric("Total Biaya", f"-${preview['Fee Total ($)']:,.2f}", "Trading + Inap", delta_color="inverse")
with m3:
    st.metric("Potensi Profit", f"${preview['Est. Profit ($)']:,.2f}", "Jika kena TP", delta_color="normal")
with m4:
    # Logic Warna Likuidasi
    dist_liq = abs(preview['Liq Price'] - entry_input) / entry_input * 100
    liq_color = "normal" if dist_liq > 50 else "off" if dist_liq > 20 else "inverse"
    st.metric("Harga Likuidasi", f"${preview['Liq Price']:,.4f}", f"Jarak {dist_liq:.1f}%", delta_color=liq_color)

# --- BAGIAN B: STATISTIK PORTFOLIO (AGREGAT) ---
if len(st.session_state['portfolio']) > 0:
    st.markdown("---")
    st.subheader("📈 Statistik Portfolio")
    
    # Convert list ke DataFrame
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # Hitung Agregat
    total_margin = df['Margin ($)'].sum()
    total_profit_pot = df['Est. Profit ($)'].sum()
    usage_pct = (total_margin / total_equity) * 100
    
    # --- HEALTH BAR (MONEY MANAGEMENT) ---
    st.markdown("##### Indikator Kesehatan Modal")
    
    # Tentukan warna
    if usage_pct < 5:
        bar_color, msg = "#00CC96", "AMAN (Conservative)"
    elif usage_pct < 20:
        bar_color, msg = "#FFAA00", "MODERATE (Aggressive)"
    else:
        bar_color, msg = "#FF4B4B", "BAHAYA (Overtrade)"
        
    st.markdown(f"""
        <div style="background-color: #262730; border-radius: 5px; margin-bottom: 5px;">
            <div style="width: {min(usage_pct, 100)}%; background-color: {bar_color}; height: 25px; border-radius: 5px; text-align: center; color: white; font-weight: bold; line-height: 25px;">
                {usage_pct:.2f}%
            </div>
        </div>
        <div style="font-size: 0.9em; color: #aaa; display: flex; justify-content: space-between;">
            <span>Terpakai: <b>${total_margin:,.2f}</b></span>
            <span>Status: <b style="color:{bar_color}">{msg}</b></span>
        </div>
    """, unsafe_allow_html=True)
    
    # Statistik Grid
    st.markdown("####")
    row1, row2, row3 = st.columns(3)
    with row1: st.metric("Total Posisi", len(df), "Trade Open")
    with row2: st.metric("Total Potensi Cuan", f"${total_profit_pot:,.2f}", "Agregat TP")
    with row3: st.metric("Sisa Saldo Aset", f"${total_equity - total_margin:,.2f}", "Available")

    # --- BAGIAN C: TABEL JURNAL ---
    st.markdown("---")
    st.subheader("📋 Daftar Riwayat Trade")
    
    # Tampilkan tabel
    st.dataframe(
        df.style.format({
            "Margin ($)": "${:,.2f}",
            "Entry": "{:,.4f}",
            "TP": "{:,.4f}",
            "SL": "{:,.4f}",
            "Liq Price": "{:,.4f}",
            "Fee Total ($)": "${:,.2f}",
            "Est. Profit ($)": "${:,.2f}",
            "Est. Loss/Risk ($)": "${:,.2f}"
        }),
        use_container_width=True,
        height=300
    )
    
    # --- BAGIAN D: EXPORT EXCEL ---
    st.markdown("### 📥 Download Laporan")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Jurnal Trading')
        
    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        st.download_button(
            label="Download Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"Trading_Journal_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    # Tampilan jika kosong
    st.markdown("---")
    st.info("👋 Portfolio Kosong. Masukkan setup trade di sidebar kiri lalu klik 'Tambah ke Portfolio'.")
