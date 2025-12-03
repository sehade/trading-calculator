import streamlit as st
import pandas as pd
from datetime import datetime
import io
import uuid

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="Ultimate Trading Manager V6",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
    }
    /* Tombol Update Besar (Mobile Friendly) */
    .big-button {
        width: 100%;
        padding: 15px;
        font-weight: bold;
        border-radius: 10px;
    }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE (SESSION STATE)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. LOGIKA UTAMA (THE BRAIN)
# ==========================================
def process_trade_logic(
    id_trade, timestamp, coin, status, margin_mode, total_equity, pos_type, 
    margin, lev, avg_entry, manual_last_price, tp, sl, fee_pct, fund_rate, days
):
    # Validasi
    if avg_entry <= 0: return None
    
    # A. TENTUKAN LAST PRICE & KATEGORI PNL BERDASARKAN STATUS
    # Ini logika inti yang memisahkan Running vs Closed
    
    is_running = False
    final_price = manual_last_price # Default
    
    if status == "🟢 Running":
        is_running = True
        final_price = manual_last_price # Pakai input user
    elif status == "🚀 Hit TP":
        final_price = tp # Kunci ke TP
    elif status == "⚠️ Hit SL":
        final_price = sl # Kunci ke SL
    elif status == "🏁 Closed":
        final_price = manual_last_price # Pakai input Exit Price user
        
    # B. HITUNG SIZE & FEE
    pos_size = margin * lev
    qty = pos_size / avg_entry
    
    trade_fee = pos_size * (fee_pct / 100)
    fund_fee = pos_size * (fund_rate / 100) * days
    total_fee = trade_fee + fund_fee
    
    # C. HITUNG PNL RAW (KOTOR)
    if "Long" in pos_type:
        pnl_raw = (final_price - avg_entry) * qty
    else: # Short
        pnl_raw = (avg_entry - final_price) * qty
        
    # PnL Bersih (Net)
    pnl_net = pnl_raw - total_fee
    roe_pct = (pnl_raw / margin) * 100 # ROE biasanya dari Gross PnL

    # D. FORMAT TAMPILAN (WARNA MERAH/HIJAU)
    pnl_str = f"{roe_pct:.1f}% (${pnl_net:.2f})"
    if pnl_net >= 0:
        pnl_display = f"🟢 +{pnl_str}"
    else:
        pnl_display = f"🔴 {pnl_str}"

    # E. PEMISAHAN FLOATING VS REALIZED
    floating_display = "-"
    realized_display = "-"
    realized_val = 0.0
    floating_val = 0.0
    
    if is_running:
        floating_display = pnl_display
        floating_val = pnl_net
    else:
        realized_display = pnl_display
        realized_val = pnl_net

    # F. HITUNG LIKUIDASI
    if margin_mode == "Isolated Margin":
        risk_capital = margin
    else:
        risk_capital = total_equity - total_fee
        
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, avg_entry - buffer)
    else:
        liq_price = avg_entry + buffer

    # RETURN DATA LENGKAP
    return {
        "ID": id_trade,
        "Waktu": timestamp,
        "Pair/Coin": coin.upper(),
        "Status": status,
        "Arah": pos_type,
        "Mode": margin_mode,
        "Margin": float(margin),
        "Lev": int(lev),
        "Entry": float(avg_entry),
        "Last/Exit": float(final_price),
        "TP": float(tp),
        "SL": float(sl),
        "Liq Price": float(liq_price),
        
        # Kolom Tampilan
        "Floating PnL": floating_display,
        "Realized PnL": realized_display,
        
        # Kolom Angka (Hidden untuk perhitungan statistik)
        "_float_val": floating_val,
        "_real_val": realized_val,
        "_is_running": is_running,
        
        "Fee": float(total_fee)
    }

# ==========================================
# 4. SIDEBAR (CREATE - INPUT AWAL)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Trade Baru")
    
    # Global
    st.caption("--- Info Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # Identitas
    st.caption("--- Identitas ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    status_input = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])
    
    # Logic Input Harga Akhir
    last_price_label = "Current Price"
    if status_input == "🏁 Closed": last_price_label = "Exit Price"
    
    # Setup
    st.caption("--- Setup ---")
    pos_type = st.radio("Arah", ["Long 🟢", "Short 🔴"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1: margin_in = st.number_input("Margin ($)", value=10.0)
    with c2: lev_in = st.number_input("Lev (x)", value=20)
    
    entry_in = st.number_input("Avg Entry", value=50000.0, format="%.4f")
    
    # Input Dinamis berdasarkan Status
    last_price_in = entry_in # Default
    if status_input in ["🟢 Running", "🏁 Closed"]:
        last_price_in = st.number_input(f"{last_price_label}", value=50000.0, format="%.4f")
    
    c3, c4 = st.columns(2)
    with c3: tp_in = st.number_input("TP", value=55000.0, format="%.4f")
    with c4: sl_in = st.number_input("SL", value=48000.0, format="%.4f")

    # Fee
    with st.expander("Fee Settings"):
        fee_pct = st.number_input("Fee %", value=0.045)
        fund_rate = st.number_input("Funding %", value=0.01)
        days = st.number_input("Hari", value=0)

    st.markdown("---")
    if st.button("➕ Tambah Trade"):
        if entry_in > 0:
            new_id = str(uuid.uuid4())
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            res = process_trade_logic(
                new_id, now, coin_name, status_input, margin_mode, total_equity, 
                pos_type, margin_in, lev_in, entry_in, last_price_in, tp_in, sl_in, fee_pct, fund_rate, days
            )
            st.session_state['portfolio'].append(res)
            st.toast("Trade Berhasil Ditambahkan!", icon="✅")

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.title("💎 Ultimate Trading Manager")
    st.caption("Monitoring Floating & Rekap Kumulatif")
with c_head2:
    st.metric("Saldo Aset", f"${total_equity:,.2f}")

st.markdown("---")

if len(st.session_state['portfolio']) > 0:
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # --- A. STATISTIK KEUANGAN (LENGKAP) ---
    st.subheader("📈 Ringkasan Keuangan")
    
    # Hitung Agregat
    total_margin = df[df['_is_running'] == True]['Margin'].sum()
    total_floating = df['_float_val'].sum()
    total_realized = df['_real_val'].sum()
    
    current_real_balance = total_equity + total_realized
    projected_balance = current_real_balance + total_floating
    
    # Health Bar
    usage_pct = (total_margin / current_real_balance) * 100 if current_real_balance > 0 else 0
    if usage_pct < 5: color, msg = "#00CC96", "AMAN"
    elif usage_pct < 20: color, msg = "#FFAA00", "MODERATE"
    else: color, msg = "#FF4B4B", "BAHAYA"
    
    st.markdown(f"""
        <div style="margin-bottom:5px;">Margin Health: <b style="color:{color}">{msg}</b> ({usage_pct:.1f}%)</div>
        <div style="background:#262730; height:10px; border-radius:5px; width:100%; margin-bottom:15px;">
            <div style="background:{color}; width:{min(usage_pct, 100)}%; height:100%; border-radius:5px;"></div>
        </div>
    """, unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Floating PnL (Unrealized)", f"${total_floating:,.2f}", "Sedang Berjalan", delta_color="normal" if total_floating>=0 else "inverse")
    with m2: st.metric("Kumulatif PnL (Realized)", f"${total_realized:,.2f}", "Sudah Cair", delta_color="normal" if total_realized>=0 else "inverse")
    with m3: st.metric("Saldo Real Saat Ini", f"${current_real_balance:,.2f}", "Equity + Realized")
    with m4: st.metric("Estimasi Jika Close Semua", f"${projected_balance:,.2f}", "Projected")

    # --- B. TABEL MONITORING (READ ONLY) ---
    st.markdown("---")
    st.subheader("📋 Tabel Monitoring")
    
    # Tampilkan tabel bersih (Kolom internal _ disembunyikan)
    display_cols = ["Waktu", "Pair/Coin", "Status", "Arah", "Entry", "Last/Exit", "Floating PnL", "Realized PnL", "Liq Price"]
    st.dataframe(df[display_cols], use_container_width=True, height=250)

    # --- C. FITUR EDIT MOBILE FRIENDLY (HYBRID UI) ---
    st.markdown("---")
    st.subheader("✏️ Edit & Update Trade (Mobile Friendly)")
    
    # 1. Pilih Trade
    trade_options = df.apply(lambda x: f"{x['Pair/Coin']} ({x['Status']}) - ID:{x['ID'][:4]}", axis=1).tolist()
    selected_option = st.selectbox("Pilih Trade untuk Diedit:", trade_options)
    
    # Ambil data trade yang dipilih
    if selected_option:
        sel_index = trade_options.index(selected_option)
        sel_row = df.iloc[sel_index]
        
        with st.form("edit_form"):
            st.info(f"Mengedit: **{sel_row['Pair/Coin']}** | Arah: **{sel_row['Arah']}**")
            
            # Kolom Edit
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                new_status = st.selectbox("Update Status", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], index=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"].index(sel_row['Status']))
                new_margin = st.number_input("Update Margin ($)", value=float(sel_row['Margin']))
            
            with col_e2:
                # Logic Last Price di Form
                label_price = "Update Last Price"
                val_price = float(sel_row['Last/Exit'])
                if new_status == "🏁 Closed": label_price = "Exit Price"
                if new_status in ["🚀 Hit TP", "⚠️ Hit SL"]: label_price = "Price Locked (TP/SL)"
                
                new_price = st.number_input(label_price, value=val_price, format="%.4f", disabled=(new_status in ["🚀 Hit TP", "⚠️ Hit SL"]))
                new_entry = st.number_input("Update Avg Entry (DCA)", value=float(sel_row['Entry']), format="%.4f")

            col_e3, col_e4 = st.columns(2)
            with col_e3: new_tp = st.number_input("Update TP", value=float(sel_row['TP']), format="%.4f")
            with col_e4: new_sl = st.number_input("Update SL", value=float(sel_row['SL']), format="%.4f")
            
            # Checkbox Hapus
            delete_trade = st.checkbox("🗑️ Hapus Trade Ini Permanen")

            # TOMBOL UPDATE BESAR
            if st.form_submit_button("💾 SIMPAN PERUBAHAN", type="primary", use_container_width=True):
                if delete_trade:
                    # Logika Hapus
                    st.session_state['portfolio'].pop(sel_index)
                    st.rerun()
                else:
                    # Logika Update
                    # Ambil data lama + update data baru
                    updated_data = process_trade_logic(
                        sel_row['ID'], sel_row['Waktu'], sel_row['Pair/Coin'], 
                        new_status, sel_row['Mode'], total_equity, sel_row['Arah'], 
                        new_margin, sel_row['Lev'], new_entry, new_price, 
                        new_tp, new_sl, fee_pct, fund_rate, days
                    )
                    st.session_state['portfolio'][sel_index] = updated_data
                    st.rerun()

    # --- D. EXPORT EXCEL ---
    st.markdown("---")
    st.subheader("📥 Download Laporan")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export = df.drop(columns=["_float_val", "_real_val", "_is_running"])
        df_export.to_excel(writer, index=False, sheet_name='Journal')
        
    st.download_button("Download Excel (.xlsx)", buffer.getvalue(), f"Journal_{datetime.now().strftime('%Y%m%d')}.xlsx")

else:
    st.info("👋 Belum ada data. Silakan input trade baru di Sidebar.")
