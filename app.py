import streamlit as st

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Kalkulator Trading Pro",
    page_icon="📈",
    layout="wide"
)

# --- JUDUL UTAMA ---
st.title("📈 Kalkulator Trading & Manajemen Risiko")
st.markdown("---")

# --- SIDEBAR (INPUT USER) ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Trade")
    
    # 1. Tipe Posisi
    position_type = st.radio("Tipe Posisi", ["Long (Buy)", "Short (Sell)"], horizontal=True)
    
    # 2. Margin & Leverage
    col1, col2 = st.columns(2)
    with col1:
        margin = st.number_input("Margin (USDT)", min_value=1.0, value=100.0, step=10.0)
    with col2:
        leverage = st.number_input("Leverage (x)", min_value=1, max_value=250, value=10, step=1)
        
    # 3. Harga (Price Inputs)
    st.subheader("Titik Harga")
    entry_price = st.number_input("Harga Entry (Masuk)", min_value=0.000001, value=50000.0, format="%.6f")
    
    # Target & Stop Loss
    col3, col4 = st.columns(2)
    with col3:
        target_price = st.number_input("Target Price (TP)", min_value=0.0, value=55000.0, format="%.6f")
    with col4:
        stop_loss = st.number_input("Stop Loss (SL)", min_value=0.0, value=48000.0, format="%.6f")
        
    # 4. Pengaturan Biaya (Fee & Funding)
    st.subheader("💰 Pengaturan Biaya")
    
    # Biaya Trading (Handling Fee)
    fee_percent = st.number_input(
        "Tingkat Biaya Trading (%)", 
        min_value=0.0, 
        value=0.045, 
        step=0.001, 
        format="%.4f",
        help="Sesuai aturan: Biaya = Margin * Lev * Rate. Gratis saat open, bayar saat close."
    )
    
    st.caption("--- Biaya Inap (Funding) ---")
    
    # Biaya Inap (Funding Fee)
    col_fund1, col_fund2 = st.columns(2)
    with col_fund1:
        funding_rate = st.number_input(
            "Rate/Hari (%)", 
            min_value=0.0, 
            value=0.0, 
            step=0.01, 
            help="Biaya inap per hari dalam persen. Kosongkan jika intraday (0 hari)."
        )
    with col_fund2:
        holding_days = st.number_input(
            "Lama Hold (Hari)", 
            min_value=0, 
            value=0, 
            step=1,
            help="Berapa hari posisi dibiarkan terbuka."
        )

# --- LOGIKA PERHITUNGAN (BACKEND) ---
if entry_price > 0:
    # A. Dasar Perhitungan
    position_size = margin * leverage # Total nilai posisi (Notional Value)
    quantity = position_size / entry_price # Jumlah koin/aset yang didapat
    
    # B. Hitung Biaya (Fee Logic Update)
    
    # 1. Biaya Trading (Handling Fee)
    # Sesuai gambar: Rumus = Margin * Leverage * Rate
    # Dan hanya dibebankan sekali (saat tutup).
    trading_fee = position_size * (fee_percent / 100)
    
    # 2. Biaya Pendanaan (Funding Fee / Biaya Inap)
    # Rumus = Position Size * Rate Harian * Jumlah Hari
    funding_fee = position_size * (funding_rate / 100) * holding_days
    
    # 3. Total Biaya
    total_fee = trading_fee + funding_fee
    
    # C. Perhitungan PnL (Profit and Loss)
    if position_type == "Long (Buy)":
        # Rumus Long: (Harga Jual - Harga Beli) * Jumlah Koin
        gross_pnl = (target_price - entry_price) * quantity
        sl_loss = (stop_loss - entry_price) * quantity
        
        # Likuidasi Long: Entry - (Entry / Leverage)
        liq_price = entry_price - (entry_price / leverage) 
        
        # Break Even Point (BEP)
        # Harga harus naik sekian untuk menutup Total Fee (Trading + Funding)
        fee_cost_per_unit = total_fee / quantity
        bep_price = entry_price + fee_cost_per_unit

    else: # Short (Sell)
        # Rumus Short: (Harga Masuk - Harga Keluar) * Jumlah Koin
        gross_pnl = (entry_price - target_price) * quantity
        sl_loss = (entry_price - stop_loss) * quantity
        
        # Likuidasi Short: Entry + (Entry / Leverage)
        liq_price = entry_price + (entry_price / leverage)
        
        # Break Even Point (BEP) Short
        fee_cost_per_unit = total_fee / quantity
        bep_price = entry_price - fee_cost_per_unit

    # Net PnL (Setelah Total Biaya)
    net_pnl = gross_pnl - total_fee
    net_roe = (net_pnl / margin) * 100
    
    net_loss_sl = sl_loss - total_fee
    net_loss_roe = (net_loss_sl / margin) * 100

    # Risk Reward Ratio
    dist_reward = abs(target_price - entry_price)
    dist_risk = abs(entry_price - stop_loss)
    
    if dist_risk > 0:
        rr_ratio = dist_reward / dist_risk
    else:
        rr_ratio = 0

    # --- TAMPILAN OUTPUT (FRONTEND) ---
    
    # 1. Kartu Utama (Metrics)
    st.subheader("📊 Hasil Simulasi")
    
    col_res1, col_res2, col_res3 = st.columns(3)
    
    with col_res1:
        st.metric(label="Modal Awal (Margin)", value=f"${margin:,.2f}")
    
    with col_res2:
        st.metric(
            label="Estimasi Net Profit (TP)", 
            value=f"${net_pnl:,.2f}", 
            delta=f"{net_roe:.2f}% (ROE)",
            delta_color="normal"
        )
        
    with col_res3:
        st.metric(
            label="Total Biaya (Fee + Funding)", 
            value=f"${total_fee:,.2f}",
            delta="- Pengurang Profit",
            delta_color="inverse"
        )

    st.markdown("---")

    # 2. Rincian Biaya (Fitur Baru)
    with st.expander("🔍 Lihat Rincian Biaya (Trading + Inap)"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write("**Biaya Trading**")
            st.write(f"${trading_fee:,.2f}")
            st.caption(f"Rate: {fee_percent}%")
        with c2:
            st.write("**Biaya Inap (Funding)**")
            st.write(f"${funding_fee:,.2f}")
            st.caption(f"{holding_days} hari @ {funding_rate}%/hari")
        with c3:
            st.write("**Total Potongan**")
            st.write(f"**${total_fee:,.2f}**")

    # 3. Detail Analisis & Risiko
    col_ana1, col_ana2 = st.columns([1, 1])

    with col_ana1:
        st.info("ℹ️ **Analisis Posisi**")
        st.markdown(f"""
        - **Posisi Size:** ${position_size:,.2f}
        - **Break Even Point:** ${bep_price:,.2f} (Harga Balik Modal)
        """)

    with col_ana2:
        st.warning("⚠️ **Analisis Risiko**")
        st.markdown(f"""
        - **Harga Likuidasi (Est):** ${liq_price:,.2f}
        - **Risk to Reward:** 1 : {rr_ratio:.2f}
        - **Jika Kena SL (Net):** Rugi ${net_loss_sl:,.2f} ({net_loss_roe:.2f}%)
        """)

else:
    st.warning("Masukkan Harga Entry lebih dari 0 untuk memulai kalkulasi.")
