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
        
    # 4. Trading Fee
    st.subheader("Biaya Exchange")
    fee_percent = st.number_input("Trading Fee (%)", min_value=0.0, value=0.04, step=0.01, help="Fee rata-rata exchange (Maker+Taker). Biasanya 0.02% - 0.06%")

# --- LOGIKA PERHITUNGAN (BACKEND) ---
if entry_price > 0:
    # A. Dasar Perhitungan
    position_size = margin * leverage # Total nilai posisi
    quantity = position_size / entry_price # Jumlah koin/aset yang didapat
    
    # B. Hitung Estimasi Fee (Buka + Tutup Posisi)
    # Asumsi: Fee dihitung dari total volume trading (Entry + Exit)
    # Ini estimasi kasar karena harga exit belum terjadi, kita pakai target untuk estimasi maksimal
    total_fee = (position_size * (fee_percent / 100)) + ((quantity * target_price) * (fee_percent / 100))
    
    # C. Perhitungan PnL (Profit and Loss)
    if position_type == "Long (Buy)":
        # Rumus Long: (Harga Jual - Harga Beli) * Jumlah Koin
        gross_pnl = (target_price - entry_price) * quantity
        sl_loss = (stop_loss - entry_price) * quantity
        
        # Likuidasi Long: Entry - (Entry / Leverage)
        # Tambahan safety margin 0.5% agar tidak terlalu mepet
        liq_price = entry_price - (entry_price / leverage) 
        
        # Break Even Point (BEP): Harga harus naik sekian persen untuk tutup fee
        fee_cost_in_price = (total_fee / quantity)
        bep_price = entry_price + fee_cost_in_price

    else: # Short (Sell)
        # Rumus Short: (Harga Jual - Harga Beli) * Jumlah Koin * -1 (Atau Entry - Exit)
        gross_pnl = (entry_price - target_price) * quantity
        sl_loss = (entry_price - stop_loss) * quantity
        
        # Likuidasi Short: Entry + (Entry / Leverage)
        liq_price = entry_price + (entry_price / leverage)
        
        # Break Even Point (BEP) Short
        fee_cost_in_price = (total_fee / quantity)
        bep_price = entry_price - fee_cost_in_price

    # Net PnL (Setelah Fee)
    net_pnl = gross_pnl - total_fee
    net_roe = (net_pnl / margin) * 100
    
    net_loss_sl = sl_loss - total_fee
    net_loss_roe = (net_loss_sl / margin) * 100

    # Risk Reward Ratio
    # Risk = Jarak Entry ke SL | Reward = Jarak Entry ke TP
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
        color = "normal"
        if net_pnl > 0: color = "off" # Streamlit metric auto color logic handling is limited, we use delta
        st.metric(
            label="Estimasi Net Profit (TP)", 
            value=f"${net_pnl:,.2f}", 
            delta=f"{net_roe:.2f}% (ROE)",
            delta_color="normal" # Hijau jika positif
        )
        
    with col_res3:
        st.metric(
            label="Estimasi Total Fee", 
            value=f"${total_fee:,.2f}",
            delta="- Biaya Exchange",
            delta_color="inverse"
        )

    st.markdown("---")

    # 2. Detail Analisis & Risiko
    col_ana1, col_ana2 = st.columns([1, 1])

    with col_ana1:
        st.info("ℹ️ **Analisis Posisi**")
        st.markdown(f"""
        - **Posisi Size:** ${position_size:,.2f}
        - **Quantity:** {quantity:.6f} Coin
        - **Break Even Price:** ${bep_price:,.2f} (Titik Balik Modal)
        """)

    with col_ana2:
        st.warning("⚠️ **Analisis Risiko**")
        st.markdown(f"""
        - **Harga Likuidasi (Est):** ${liq_price:,.2f}
        - **Risk to Reward:** 1 : {rr_ratio:.2f}
        - **Jika Kena SL:** Rugi ${net_loss_sl:,.2f} ({net_loss_roe:.2f}%)
        """)

    # 3. Visualisasi Sederhana R:R
    st.subheader("Visualisasi Risk/Reward")
    if rr_ratio >= 2:
        st.success(f"✅ Trade Bagus! Rasio 1 : {rr_ratio:.2f} (Reward jauh lebih besar dari Risk)")
    elif 1 <= rr_ratio < 2:
        st.warning(f"⚠️ Trade Menengah. Rasio 1 : {rr_ratio:.2f}")
    else:
        st.error(f"❌ Trade Berbahaya. Rasio 1 : {rr_ratio:.2f} (Risk lebih besar atau hampir sama dengan Reward)")

else:
    st.warning("Masukkan Harga Entry lebih dari 0 untuk memulai kalkulasi.")
