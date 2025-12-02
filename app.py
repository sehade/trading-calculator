import streamlit as st

# --- 1. KONFIGURASI HALAMAN (Harus di paling atas) ---
st.set_page_config(
    page_title="Kalkulator Trading Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOM (Mempercantik Tampilan) ---
st.markdown("""
<style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    div[data-testid="stExpander"] div[role="button"] p { font-size: 1.1rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR (INPUT DATA) ---
with st.sidebar:
    st.title("🎛️ Panel Kontrol")
    
    # Section A: Saldo
    st.markdown("### 1. Informasi Modal")
    total_equity = st.number_input(
        "Total Saldo Aset (USDT)", 
        min_value=1.0, value=1000.0, step=100.0,
        help="Total uang di wallet sebelum trade."
    )

    # Section B: Setup Trade
    st.markdown("### 2. Setup Posisi")
    position_type = st.radio("Arah Market", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True)
    
    c1, c2 = st.columns(2)
    with c1:
        margin = st.number_input("Margin (USDT)", min_value=1.0, value=10.0, step=10.0)
    with c2:
        leverage = st.number_input("Leverage (x)", min_value=1, max_value=250, value=10)

    # Section C: Harga
    st.markdown("### 3. Entry & Exit")
    entry_price = st.number_input("Harga Entry", min_value=0.000001, value=50000.0, format="%.6f")
    
    c3, c4 = st.columns(2)
    with c3:
        target_price = st.number_input("Target (TP)", value=55000.0, format="%.6f")
    with c4:
        stop_loss = st.number_input("Stop Loss (SL)", value=48000.0, format="%.6f", help="Isi 0 jika tanpa SL")

    # Section D: Biaya (Fee)
    st.markdown("### 4. Potongan Biaya")
    with st.expander("⚙️ Atur Fee & Funding"):
        fee_percent = st.number_input("Fee Trading (%)", value=0.045, step=0.001, format="%.4f")
        st.caption("Biaya Inap (Funding):")
        funding_rate = st.number_input("Rate/Hari (%)", value=0.01, step=0.01)
        holding_days = st.number_input("Lama Hold (Hari)", value=0, step=1)

# --- 4. LOGIKA UTAMA (BACKEND) ---
if entry_price > 0:
    # --- HITUNG SIZE & FEE ---
    position_size = margin * leverage 
    quantity = position_size / entry_price 
    
    # Hitung Fee sesuai request (Trading Fee hanya saat close + Funding Fee)
    trading_fee = position_size * (fee_percent / 100)
    funding_fee = position_size * (funding_rate / 100) * holding_days
    total_fee = trading_fee + funding_fee
    
    # --- HITUNG PNL & LIKUIDASI ---
    if "Long" in position_type:
        gross_pnl_tp = (target_price - entry_price) * quantity
        # Jika SL 0, rugi maksimal adalah Margin (Likuidasi)
        gross_pnl_sl = (stop_loss - entry_price) * quantity if stop_loss > 0 else -margin
        liq_price = entry_price - (entry_price / leverage)
        
        # Jarak aman SL
        is_sl_safe = stop_loss > liq_price if stop_loss > 0 else False
        
    else: # Short
        gross_pnl_tp = (entry_price - target_price) * quantity
        gross_pnl_sl = (entry_price - stop_loss) * quantity if stop_loss > 0 else -margin
        liq_price = entry_price + (entry_price / leverage)
        
        # Jarak aman SL
        is_sl_safe = stop_loss < liq_price if stop_loss > 0 else False

    # Net PnL (Potong Fee)
    net_pnl_tp = gross_pnl_tp - total_fee
    net_pnl_sl = gross_pnl_sl - total_fee
    
    # ROE %
    roe_tp = (net_pnl_tp / margin) * 100
    roe_sl = (net_pnl_sl / margin) * 100

    # Risk Reward Logic
    dist_reward = abs(target_price - entry_price)
    dist_risk = abs(entry_price - stop_loss) if stop_loss > 0 else abs(entry_price - liq_price)
    rr_ratio = dist_reward / dist_risk if dist_risk > 0 else 0

    # Money Management Logic
    margin_usage_percent = (margin / total_equity) * 100
    safe_margin_limit = 1.0 # Batas aman 1%

    # --- 5. TAMPILAN UTAMA (FRONTEND) ---
    st.header(f"📊 Analisis Posisi: {position_type}")
    
    # [VISUAL 1] MONEY MANAGEMENT BAR
    st.subheader("🛡️ Kesehatan Modal")
    
    col_risk1, col_risk2 = st.columns([3, 1])
    with col_risk1:
        # Progress bar logic
        risk_val = min(margin_usage_percent / 5, 1.0) # Scale 0-5% (5% = penuh)
        
        if margin_usage_percent <= 1:
            bar_color = "green"
            status_msg = "✅ AMAN (Conservative)"
        elif margin_usage_percent <= 3:
            bar_color = "yellow" 
            status_msg = "⚠️ HATI-HATI (Aggressive)"
        else:
            bar_color = "red"
            status_msg = "🚨 BAHAYA (Gambling)"
            
        st.write(f"Penggunaan Modal: **{margin_usage_percent:.2f}%** | Status: **{status_msg}**")
        st.progress(risk_val) # Streamlit native progress bar
        
    with col_risk2:
        st.metric("Sisa Saldo Aman", f"${total_equity - margin:,.2f}")

    st.markdown("---")

    # [VISUAL 2] KARTU HASIL (METRICS)
    st.subheader("💰 Proyeksi Profit & Loss")
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Modal (Margin)", f"${margin:,.2f}", f"{leverage}x Lev")
    with m2:
        st.metric("Fee Exchange", f"-${total_fee:,.2f}", "Trading + Inap", delta_color="inverse")
    with m3:
        st.metric("Profit Bersih (TP)", f"${net_pnl_tp:,.2f}", f"{roe_tp:.1f}%", delta_color="normal")
    with m4:
        # Logic warna SL
        sl_val = f"${net_pnl_sl:,.2f}"
        sl_delta = f"{roe_sl:.1f}%"
        st.metric("Loss Bersih (SL)", sl_val, sl_delta, delta_color="inverse")

    # [VISUAL 3] SALDO AKHIR
    st.info(f"""
    **🔮 Simulasi Rekening:**
    - Saldo Awal: **${total_equity:,.2f}**
    - Jika Profit (TP): **${total_equity + net_pnl_tp:,.2f}** 🚀
    - Jika Rugi (SL): **${total_equity + net_pnl_sl:,.2f}** 🔻
    """)

    st.markdown("---")

    # [VISUAL 4] DETAIL TEKNIS (KOLOM INFO)
    c_info1, c_info2 = st.columns(2)
    
    with c_info1:
        st.warning("⚠️ **Zona Bahaya (Likuidasi)**")
        st.write(f"Harga Likuidasi: **${liq_price:,.2f}**")
        
        # Cek Keamanan SL
        if stop_loss == 0:
            st.error("⛔ ANDA TIDAK PASANG SL! Modal bisa ludes.")
        elif not is_sl_safe:
            st.error(f"❌ SL SALAH POSISI! Anda akan likuidasi (${liq_price:,.2f}) sebelum kena SL.")
        else:
            st.success("✅ SL AMAN (Di atas/bawah likuidasi).")

    with c_info2:
        st.success("🎯 **Rasio Risk & Reward**")
        st.write(f"Risk : Reward = **1 : {rr_ratio:.2f}**")
        
        # Break Even Point
        # Harga BEP = Entry +/- (Total Fee / Quantity)
        fee_shift = total_fee / quantity
        if "Long" in position_type:
            bep = entry_price + fee_shift
        else:
            bep = entry_price - fee_shift
            
        st.write(f"Harga Balik Modal (BEP): **${bep:,.2f}**")

else:
    st.info("👈 Silakan masukkan data trade di Sidebar sebelah kiri.")
