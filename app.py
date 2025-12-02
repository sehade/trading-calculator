import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 1. KONFIGURASI HALAMAN & TEMA MODERN ---
st.set_page_config(
    page_title="Pro Trader Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOM (MODERN DARK UI) ---
st.markdown("""
<style>
    /* Styling Container Utama */
    .main {
        background-color: #0e1117;
    }
    /* Card Style untuk Metrics */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
    }
    /* Judul font */
    h1, h2, h3 {
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
    }
    /* Tabel Modern */
    div[data-testid="stDataFrame"] {
        border: 1px solid #41424C;
        border-radius: 10px;
    }
    /* Tombol Primary (Tambah) */
    div.stButton > button:first-child {
        background-color: #00CC96;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        padding: 0.5rem 1rem;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #00a87d;
        border: none;
        color: white;
    }
    /* Custom Progress Bar Colors */
    .stProgress > div > div > div > div {
        background-color: #00CC96;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE (DATABASE SEMENTARA) ---
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# --- 4. ENGINE PERHITUNGAN (BACKEND) ---
def calculate_trade(margin_mode, total_equity, pos_type, margin, lev, entry, tp, sl, fee_pct, fund_rate, days):
    # Hitung Size
    pos_size = margin * lev
    qty = pos_size / entry
    
    # Hitung Fee (Trading + Funding)
    trade_fee = pos_size * (fee_pct / 100)
    fund_fee = pos_size * (fund_rate / 100) * days
    total_fee = trade_fee + fund_fee
    
    # Hitung Likuidasi & PnL
    # Logika Cross vs Isolated
    if margin_mode == "Isolated Margin":
        risk_capital = margin
    else: # Cross Margin
        # Estimasi konservatif: Saldo dikurangi fee dulu
        risk_capital = total_equity - total_fee 
        
    buffer = risk_capital / qty
    
    if "Long" in pos_type:
        liq = max(0, entry - buffer)
        pnl_gross = (tp - entry) * qty
        # Jika SL 0, dianggap hold sampai likuidasi (max loss = risk capital)
        sl_loss_gross = (sl - entry) * qty if sl > 0 else -risk_capital
    else: # Short
        liq = entry + buffer
        pnl_gross = (entry - tp) * qty
        sl_loss_gross = (entry - sl) * qty if sl > 0 else -risk_capital

    net_profit = pnl_gross - total_fee
    net_loss = sl_loss_gross - total_fee
    
    return {
        "Waktu": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Mode": margin_mode,
        "Posisi": pos_type,
        "Margin ($)": margin,
        "Lev (x)": lev,
        "Entry": entry,
        "TP": tp,
        "SL": sl,
        "Liq Price": liq,
        "Fee ($)": total_fee,
        "Profit ($)": net_profit,
        "Risk/Loss ($)": net_loss
    }

# --- 5. SIDEBAR (INPUT PANEL) ---
with st.sidebar:
    st.title("🎛️ Trade Control")
    st.markdown("---")
    
    # A. Akun
    st.markdown("### 1. Info Dompet")
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])
    total_equity = st.number_input("Saldo Aset (USDT)", value=1000.0, step=50.0)

    # B. Posisi
    st.markdown("### 2. Setup Posisi")
    pos_type = st.radio("Arah", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True, label_visibility="collapsed")
    
    c1, c2 = st.columns(2)
    with c1: margin_input = st.number_input("Margin ($)", value=10.0, min_value=1.0)
    with c2: lev_input = st.number_input("Lev (x)", value=20, min_value=1, max_value=250)
    
    entry_input = st.number_input("Harga Entry", value=50000.0, format="%.4f", min_value=0.0001)
    
    c3, c4 = st.columns(2)
    with c3: tp_input = st.number_input("Target (TP)", value=52000.0, format="%.4f")
    with c4: sl_input = st.number_input("Stop Loss", value=49000.0, format="%.4f", help="0 = Tanpa SL")

    # C. Fee
    with st.expander("⚙️ Setting Biaya (Fee)"):
        fee_pct = st.number_input("Fee Trading (%)", value=0.045, step=0.001, format="%.3f")
        fund_rate = st.number_input("Funding/Hari (%)", value=0.010, step=0.001, format="%.3f")
        days = st.number_input("Hold (Hari)", value=0, min_value=0)

    # D. Tombol Eksekusi
    st.markdown("---")
    if st.button("➕ Tambah ke Portfolio"):
        if entry_input > 0:
            res = calculate_trade(margin_mode, total_equity, pos_type, margin_input, lev_input, entry_input, tp_input, sl_input, fee_pct, fund_rate, days)
            st.session_state['portfolio'].append(res)
            st.success("Posisi berhasil ditambahkan!")
        else:
            st.error("Harga Entry tidak boleh 0")

    if st.button("🗑️ Reset Data"):
        st.session_state['portfolio'] = []
        st.rerun()

# --- 6. DASHBOARD UTAMA (UI MODERN) ---

# Header Area
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("⚡ Pro Trader Dashboard")
    st.caption(f"Saldo Aset: ${total_equity:,.2f} | Mode Aktif: **{margin_mode}**")
with col_h2:
    # Menampilkan Jam Server
    st.metric("Waktu Server", datetime.now().strftime("%H:%M"))

st.markdown("---")

# === BAGIAN 1: STATISTIK REAL-TIME (PREVIEW) ===
st.subheader("🔍 Analisis Live (Preview)")

# Hitung preview trade yang sedang diketik user (tanpa simpan)
preview = calculate_trade(margin_mode, total_equity, pos_type, margin_input, lev_input, entry_input, tp_input, sl_input, fee_pct, fund_rate, days)

# Tampilkan dalam 4 Kartu Metrik
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Modal (Margin)", f"${preview['Margin ($)']:,.2f}", f"{lev_input}x Lev")
with m2:
    st.metric("Estimasi Fee", f"-${preview['Fee ($)']:,.2f}", "Trading + Inap", delta_color="inverse")
with m3:
    st.metric("Potensi Profit", f"${preview['Profit ($)']:,.2f}", "Jika kena TP", delta_color="normal")
with m4:
    # Logic warna Likuidasi
    liq_dist = abs(preview['Liq Price'] - entry_input) / entry_input * 100
    if liq_dist > 50:
        liq_color = "normal" # Hijau (Aman)
    elif liq_dist > 20:
        liq_color = "off"    # Abu (Warning)
    else:
        liq_color = "inverse" # Merah (Bahaya)
        
    st.metric("Likuidasi", f"${preview['Liq Price']:,.2f}", f"Jarak {liq_dist:.1f}%", delta_color=liq_color)

# === BAGIAN 2: STATISTIK PORTFOLIO (AGREGAT) ===
if len(st.session_state['portfolio']) > 0:
    st.markdown("---")
    st.subheader("📈 Statistik Portfolio Global")
    
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # Hitung Agregat Data
    total_margin_used = df['Margin ($)'].sum()
    total_pot_profit = df['Profit ($)'].sum()
    total_risk = df['Risk/Loss ($)'].sum()
    margin_usage_pct = (total_margin_used / total_equity) * 100
    
    # --- HEALTH BAR (Money Management) ---
    st.markdown("##### Indikator Kesehatan Modal")
    
    # Tentukan warna bar berdasarkan risiko
    if margin_usage_pct < 5:
        bar_color = "#00CC96" # Hijau
        status_msg = "AMAN (Conservative)"
    elif margin_usage_pct < 20:
        bar_color = "#FFAA00" # Kuning
        status_msg = "HATI-HATI (Moderate)"
    else:
        bar_color = "#FF4B4B" # Merah
        status_msg = "BAHAYA (Overtrade)"

    # HTML Progress Bar Custom
    st.markdown(f"""
        <div style="background-color: #262730; border-radius: 5px; margin-bottom: 5px;">
            <div style="width: {min(margin_usage_pct, 100)}%; background-color: {bar_color}; height: 25px; border-radius: 5px; text-align: center; color: white; font-weight: bold; line-height: 25px;">
                {margin_usage_pct:.2f}%
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #aaa;">
            <span>Terpakai: <b>${total_margin_used:,.2f}</b></span>
            <span>Status: <b style="color:{bar_color}">{status_msg}</b></span>
            <span>Sisa Saldo: <b>${total_equity - total_margin_used:,.2f}</b></span>
        </div>
    """, unsafe_allow_html=True)

    # Statistik Row
    st.markdown("####")
    row1, row2, row3 = st.columns(3)
    with row1:
        st.metric("Total Posisi Aktif", len(df), "Trade Open")
    with row2:
        st.metric("Total Potensi Cuan", f"${total_pot_profit:,.2f}", "Agregat TP")
    with row3:
        st.metric("Total Risiko Max", f"${total_risk:,.2f}", "Agregat SL/Liq", delta_color="inverse")

    # === BAGIAN 3: JURNAL TRADING (TABEL) ===
    st.markdown("---")
    st.subheader("📋 Jurnal Trading")
    
    # Format Tampilan Tabel
    st.dataframe(
        df.style.format({
            "Margin ($)": "${:,.2f}",
            "Entry": "{:,.4f}",
            "TP": "{:,.4f}",
            "SL": "{:,.4f}",
            "Liq Price": "{:,.4f}",
            "Fee ($)": "${:,.2f}",
            "Profit ($)": "${:,.2f}",
            "Risk/Loss ($)": "${:,.2f}",
        }),
        use_container_width=True,
        height=300
    )
    
    # === BAGIAN 4: EXPORT EXCEL ===
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Trade Log')
        
    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        st.download_button(
            label="📥 Download Laporan Excel",
            data=buffer.getvalue(),
            file_name=f"Trade_Journal_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

else:
    # Tampilan Kosong (Placeholder)
    st.markdown("---")
    st.info("👋 Portfolio Kosong. Masukkan setup trade di sidebar kiri lalu klik 'Tambah ke Portfolio' untuk memulai.")
