import streamlit as st

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Kalkulator Trading Pro (Cross/Isolated)",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CUSTOM (FIX TAMPILAN) ---
st.markdown("""
<style>
    /* Agar tulisan di expander lebih tebal */
    div[data-testid="stExpander"] div[role="button"] p { 
        font-size: 1.1rem; 
        font-weight: 600; 
    }
    /* Menghapus background paksa metric agar adaptif Dark/Light mode */
    /* Memberi warna khusus pada error message container */
    div[data-testid="stAlert"] {
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. SIDEBAR (INPUT DATA) ---
with st.sidebar:
    st.title("🎛️ Panel Kontrol")
    
    # --- PILIHAN MODE MARGIN (KUNCI UTAMA) ---
    st.markdown("### 1. Mode Margin")
    margin_mode = st.selectbox(
        "Tipe Margin", 
        ["Isolated Margin", "Cross Margin"],
        help="Isolated: Resiko dibatasi Margin. Cross: Resiko memakan seluruh Saldo Aset."
    )
    
    # Section Saldo
    st.markdown("### 2. Informasi Modal")
    total_equity = st.number_input(
        "Total Saldo Aset (USDT)", 
        min_value=1.0, value=500.0, step=100.0,
        help="Total uang di wallet Anda."
    )

    # Section Setup Posisi
    st.markdown("### 3. Setup Posisi")
    position_type = st.radio("Arah Market", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True)
    
    c1, c2 = st.columns(2)
    with c1:
        margin = st.number_input("Margin Awal (USDT)", min_value=1.0, value=10.0, step=5.0)
    with c2:
        leverage = st.number_input("Leverage (x)", min_value=1, max_value=250, value=20)

    # Section Harga
    st.markdown("### 4. Entry & Exit")
    entry_price = st.number_input("Harga Entry", min_value=0.000001, value=360.0, format="%.6f")
    
    c3, c4 = st.columns(2)
    with c3:
        target_price = st.number_input("Target (TP)", value=340.0, format="%.6f") # Default contoh short
    with c4:
        stop_loss = st.number_input("Stop Loss (SL)", value=0.0, format="%.6f", help="Isi 0 jika tidak pakai SL")

    # Section Fee
    with st.expander("⚙️ Atur Fee & Funding"):
        fee_percent = st.number_input("Fee Trading (%)", value=0.045, step=0.001, format="%.4f")
        funding_rate = st.number_input("Rate Funding/Hari (%)", value=0.01, step=0.01)
        holding_days = st.number_input("Lama Hold (Hari)", value=0, step=1)

# --- 4. LOGIKA PERHITUNGAN (BACKEND) ---
if entry_price > 0:
    # --- A. HITUNG SIZE ---
    position_size = margin * leverage 
    quantity = position_size / entry_price 
    
    # Hitung Fee
    trading_fee = position_size * (fee_percent / 100)
    funding_fee = position_size * (funding_rate / 100) * holding_days
    total_fee = trading_fee + funding_fee
    
    # --- B. LOGIKA LIKUIDASI (ISOLATED VS CROSS) ---
    # Logic: Berapa modal yang "Boleh Hilang" sebelum exchange menutup paksa?
    
    if margin_mode == "Isolated Margin":
        # Isolated: Modal yang dipertaruhkan HANYA Margin awal
        risk_capital = margin
    else:
        # Cross: Modal yang dipertaruhkan adalah TOTAL SALDO - Fee
        # (Kita kurangi fee dulu agar estimasi lebih aman/konservatif)
        risk_capital = total_equity - total_fee

    # Berapa jarak harga yang bisa ditahan oleh risk_capital?
    # Rumus: Jarak Harga = Modal Risiko / Jumlah Koin
    price_buffer = risk_capital / quantity
    
    if "Long" in position_type:
        # Long: Likuidasi ada di BAWAH Entry
        liq_price = entry_price - price_buffer
        if liq_price < 0: liq_price = 0 # Harga tidak bisa minus
        
        # PnL Long
        gross_pnl_tp = (target_price - entry_price) * quantity
        # Jika kena SL hitung loss, jika tidak SL loss = risk capital (likuidasi)
        gross_pnl_sl = (stop_loss - entry_price) * quantity if stop_loss > 0 else -risk_capital
        
        # Cek SL Safe Long (SL harus lebih besar dari Liq Price)
        is_sl_safe = stop_loss > liq_price if stop_loss > 0 else False

    else: # Short
        # Short: Likuidasi ada di ATAS Entry
        liq_price = entry_price + price_buffer
        
        # PnL Short
        gross_pnl_tp = (entry_price - target_price) * quantity
        gross_pnl_sl = (entry_price - stop_loss) * quantity if stop_loss > 0 else -risk_capital
        
        # Cek SL Safe Short (SL harus lebih kecil dari Liq Price)
        is_sl_safe = stop_loss < liq_price if stop_loss > 0 else False

    # Net PnL (Setelah Fee)
    net_pnl_tp = gross_pnl_tp - total_fee
    net_pnl_sl = gross_pnl_sl - total_fee 
    
    # --- 5. TAMPILAN UI (OUTPUT) ---
    st.header(f"📊 Analisis Posisi: {position_type}")
    
    # [INFO MODE]
    if margin_mode == "Cross Margin":
        st.info(f"💡 **Mode Cross Margin:** Ketahanan dana menggunakan Total Saldo Aset (**${total_equity:,.2f}**). Harga likuidasi akan sangat jauh, tapi risiko modal habis total.")
    else:
        st.warning(f"🔒 **Mode Isolated Margin:** Ketahanan dana hanya menggunakan Margin Trading (**${margin:,.2f}**). Lebih aman untuk saldo utama, tapi lebih cepat likuidasi.")

    st.markdown("---")

    # [BAGIAN 1] HARGA LIKUIDASI (ZONA KEMATIAN)
    st.subheader("💀 Zona Bahaya (Likuidasi)")
    col_liq1, col_liq2 = st.columns([1, 2])
    
    with col_liq1:
        st.metric("Harga Likuidasi", f"${liq_price:,.2f}", "Margin Call Price", delta_color="inverse")
    
    with col_liq2:
        # Hitung jarak persentase ke likuidasi
        dist_percent = abs(liq_price - entry_price) / entry_price * 100
        st.metric("Jarak Aman ke Likuidasi", f"{dist_percent:.2f}%", "Pergerakan Harga", delta_color="off")

    # Validasi SL terhadap Likuidasi
    if stop_loss > 0:
        if not is_sl_safe:
            st.error(f"❌ **SL TIDAK EFEKTIF!** Posisi Anda akan terlikuidasi di **${liq_price:,.2f}** sebelum menyentuh SL di **${stop_loss:,.2f}**. Ubah SL Anda.")
        else:
            st.success("✅ **SL AMAN.** Stop Loss berada di area aman (sebelum harga likuidasi).")
    else:
        st.error("⚠️ **TANPA STOP LOSS.** Anda bertaruh hingga harga likuidasi.")

    st.markdown("---")

    # [BAGIAN 2] PROYEKSI KEUNTUNGAN
    st.subheader("💰 Estimasi Hasil")
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Estimasi Fee", f"-${total_fee:,.2f}", "Biaya Total", delta_color="inverse")
    with m2:
        roi_tp = (net_pnl_tp / margin) * 100
        st.metric("Profit Bersih (TP)", f"${net_pnl_tp:,.2f}", f"{roi_tp:.1f}% ROI", delta_color="normal")
    with m3:
        if stop_loss > 0:
            roi_sl = (net_pnl_sl / margin) * 100
            st.metric("Loss Bersih (SL)", f"${net_pnl_sl:,.2f}", f"{roi_sl:.1f}% ROI", delta_color="inverse")
        else:
             st.metric("Loss (Likuidasi)", f"-${risk_capital:,.2f}", "Modal Hangus", delta_color="inverse")
    with m4:
        st.metric("Saldo Aset Awal", f"${total_equity:,.2f}")

    # [BAGIAN 3] SIMULASI SALDO AKHIR
    st.info(f"""
    **🔮 Simulasi Saldo Akhir (Wallet):**
    - Jika Profit (TP): **${total_equity + net_pnl_tp:,.2f}**
    - Jika Rugi (SL): **${total_equity + net_pnl_sl:,.2f}**
    - Jika Likuidasi: **${total_equity - risk_capital:,.2f}**
    """)
            
else:
    st.info("👈 Masukkan data trade di Sidebar.")
