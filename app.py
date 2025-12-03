import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import io
import uuid

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="Pro Trading Manager V9 (Time Edition)",
    page_icon="⏱️",
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
    /* Style Form Edit Mobile Friendly */
    div[data-testid="stForm"] {
        background-color: #1c1e26;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #41424C;
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
# 3. LOGIKA UTAMA (THE BRAIN V9)
# ==========================================
def calculate_duration(start_dt, end_dt):
    # Hitung selisih waktu
    diff = end_dt - start_dt
    
    # Ambil total detik
    total_seconds = diff.total_seconds()
    
    if total_seconds < 0:
        return "Error (Negatif)", 0
        
    days = int(total_seconds // 86400)
    remaining_seconds = total_seconds % 86400
    hours = int(remaining_seconds // 3600)
    
    return f"{days} Hari {hours} Jam", total_seconds

def process_trade_logic(
    id_trade, 
    start_dt, end_dt, # Parameter Waktu Baru
    coin, status, margin_mode, total_equity, pos_type, 
    margin, lev, avg_entry, manual_last_price, tp, sl, 
    input_fee_dollar, is_auto_calc_fee
):
    # Validasi
    if avg_entry <= 0: return None
    
    # A. HITUNG DURASI (TIME LOGIC)
    # Jika Running, End Time biasanya dianggap "Sekarang" untuk display durasi berjalan
    # Tapi di sini kita pakai input manual end_dt agar user bebas tentukan "Waktu Cek"
    duration_str, duration_sec = calculate_duration(start_dt, end_dt)
    
    # B. TENTUKAN LAST PRICE
    final_price = manual_last_price
    if status == "🚀 Hit TP": final_price = tp
    elif status == "⚠️ Hit SL": final_price = sl
        
    is_running = (status == "🟢 Running")

    # C. HITUNG SIZE
    pos_size = margin * lev
    qty = pos_size / avg_entry
    
    # D. LOGIKA FEE
    final_fee = input_fee_dollar
    if is_auto_calc_fee and is_running:
        final_fee = 0.0 # Default 0 kalau baru running
    
    # E. HITUNG PNL RAW
    if "Long" in pos_type:
        pnl_raw = (final_price - avg_entry) * qty
    else: # Short
        pnl_raw = (avg_entry - final_price) * qty
        
    pnl_net = pnl_raw - final_fee
    roe_pct = (pnl_raw / margin) * 100 

    # F. FORMAT TAMPILAN
    pnl_str = f"{roe_pct:.1f}% (${pnl_net:.2f})"
    if pnl_net >= 0:
        pnl_display = f"🟢 +{pnl_str}"
    else:
        pnl_display = f"🔴 {pnl_str}"

    # G. SPLIT PNL
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

    # H. HITUNG LIKUIDASI
    if margin_mode == "Isolated Margin":
        risk_capital = margin
    else:
        risk_capital = total_equity - final_fee
        
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, avg_entry - buffer)
    else:
        liq_price = avg_entry + buffer

    # RETURN DATA LENGKAP
    return {
        "ID": id_trade,
        
        # Data Waktu
        "Start Time": start_dt,
        "End Time": end_dt,
        "Durasi": duration_str, # Kolom Baru
        
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
        "Fee": float(final_fee),
        "Liq Price": float(liq_price),
        
        "Floating PnL": floating_display,
        "Realized PnL": realized_display,
        
        "_float_val": floating_val,
        "_real_val": realized_val,
        "_is_running": is_running,
    }

# ==========================================
# 4. SIDEBAR (INPUT)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Trade Baru")
    
    # 1. Info Akun
    st.caption("--- Info Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # 2. Waktu (TIME TRACKING FEATURE)
    st.caption("--- Waktu Buka Posisi ---")
    c_t1, c_t2 = st.columns(2)
    with c_t1: start_date = st.date_input("Tanggal Mulai", value="today")
    with c_t2: start_time = st.time_input("Jam Mulai", value="now")
    
    # Gabungkan date & time
    start_dt_combine = datetime.combine(start_date, start_time)

    # 3. Identitas & Status
    st.caption("--- Identitas ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    status_input = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])
    
    # Logic Label
    last_price_label = "Current Price"
    if status_input == "🏁 Closed": last_price_label = "Exit Price"
    
    # 4. Setup
    st.caption("--- Setup ---")
    pos_type = st.radio("Arah", ["Long 🟢", "Short 🔴"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1: margin_in = st.number_input("Margin ($)", value=10.0)
    with c2: lev_in = st.number_input("Lev (x)", value=20)
    
    entry_in = st.number_input("Avg Entry", value=50000.0, format="%.4f")
    
    # Input Harga Akhir
    last_price_in = entry_in 
    if status_input in ["🟢 Running", "🏁 Closed"]:
        last_price_in = st.number_input(f"{last_price_label}", value=50000.0, format="%.4f")
    
    c3, c4 = st.columns(2)
    with c3: tp_in = st.number_input("TP", value=55000.0, format="%.4f")
    with c4: sl_in = st.number_input("SL", value=48000.0, format="%.4f")

    # Fee (Optional)
    with st.expander("⚙️ Fee Est"):
        fee_pct_est = st.number_input("Est. Fee %", value=0.045)
        fee_dollar_est = (margin_in * lev_in) * (fee_pct_est / 100)
    
    st.markdown("---")
    if st.button("➕ Tambah Trade"):
        if entry_in > 0:
            new_id = str(uuid.uuid4())
            # Default End Time saat create adalah SEKARANG (untuk hitung durasi awal)
            end_dt_now = datetime.now()
            
            res = process_trade_logic(
                new_id, start_dt_combine, end_dt_now, # Kirim Waktu
                coin_name, status_input, margin_mode, total_equity, 
                pos_type, margin_in, lev_in, entry_in, last_price_in, tp_in, sl_in, 
                fee_dollar_est, True # Auto calc fee
            )
            st.session_state['portfolio'].append(res)
            st.toast("Trade Berhasil Ditambahkan!", icon="✅")
        else:
            st.error("Entry Price wajib diisi!")

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.title("⏱️ Pro Trading Manager V9")
    st.caption("Time Tracking • Floating Monitor • Realized Rekap")
with c_head2:
    st.metric("Saldo Aset", f"${total_equity:,.2f}")

st.markdown("---")

if len(st.session_state['portfolio']) > 0:
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # --- A. STATISTIK KEUANGAN ---
    st.subheader("📈 Ringkasan")
    
    total_margin = df[df['_is_running'] == True]['Margin'].sum()
    total_floating = df['_float_val'].sum()
    total_realized = df['_real_val'].sum()
    total_fees = df['Fee'].sum()
    
    curr_bal = total_equity + total_realized
    proj_bal = curr_bal + total_floating
    
    # Health Bar Logic
    usage_pct = (total_margin / curr_bal) * 100 if curr_bal > 0 else 0
    if usage_pct < 5: color, msg = "#00CC96", "AMAN"
    elif usage_pct < 20: color, msg = "#FFAA00", "MODERATE"
    else: color, msg = "#FF4B4B", "BAHAYA"
    
    st.markdown(f"""
        <div style="margin-bottom:5px;">Margin Safety: <b style="color:{color}">{msg}</b> ({usage_pct:.1f}%)</div>
        <div style="background:#262730; height:10px; border-radius:5px; width:100%; margin-bottom:15px;">
            <div style="background:{color}; width:{min(usage_pct, 100)}%; height:100%; border-radius:5px;"></div>
        </div>
    """, unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Floating PnL", f"${total_floating:,.2f}", delta_color="normal" if total_floating>=0 else "inverse")
    with m2: st.metric("Kumulatif PnL", f"${total_realized:,.2f}", delta_color="normal" if total_realized>=0 else "inverse")
    with m3: st.metric("Saldo Real", f"${curr_bal:,.2f}")
    with m4: st.metric("Total Fee", f"-${total_fees:,.2f}")

    # --- B. TABEL MONITORING (TIME EDITION) ---
    st.markdown("---")
    st.subheader("📋 Tabel Monitoring")
    
    # Format kolom waktu agar rapi
    df['Waktu Buka'] = df['Start Time'].dt.strftime('%d-%b %H:%M')
    
    display_cols = [
        "Waktu Buka", "Durasi", "Pair/Coin", "Status", "Arah", 
        "Margin", "Entry", "Last/Exit", "Fee",
        "Floating PnL", "Realized PnL"
    ]
    
    st.dataframe(
        df[display_cols].style.format({
            "Margin": "${:,.2f}",
            "Entry": "{:,.4f}",
            "Last/Exit": "{:,.4f}",
            "Fee": "${:,.2f}",
        }), 
        use_container_width=True, 
        height=300
    )

    # --- C. FITUR EDIT & TIME UPDATE (MOBILE FRIENDLY) ---
    st.markdown("---")
    st.subheader("✏️ Update Trade & Waktu")
    
    trade_options = df.apply(lambda x: f"{x['Pair/Coin']} ({x['Status']}) - {x['Durasi']}", axis=1).tolist()
    selected_option = st.selectbox("Pilih Trade:", trade_options)
    
    if selected_option:
        sel_index = trade_options.index(selected_option)
        sel_row = df.iloc[sel_index]
        
        with st.form("edit_form"):
            st.info(f"**{sel_row['Pair/Coin']}** | Status: **{sel_row['Status']}**")
            
            # 1. EDIT WAKTU & DURASI
            st.markdown("##### ⏱️ Update Waktu")
            c_time1, c_time2 = st.columns(2)
            
            # Ambil nilai lama
            old_start = pd.to_datetime(sel_row['Start Time'])
            old_end = pd.to_datetime(sel_row['End Time'])
            
            with c_time1:
                new_start_d = st.date_input("Tanggal Mulai", value=old_start.date())
                new_start_t = st.time_input("Jam Mulai", value=old_start.time())
                new_start_dt = datetime.combine(new_start_d, new_start_t)
                
            with c_time2:
                # Jika running, biasanya kita mau update 'End Time' ke 'Sekarang' untuk lihat durasi terkini
                label_end = "Waktu Akhir / Cek Sekarang"
                new_end_d = st.date_input("Tanggal Selesai/Cek", value=old_end.date())
                new_end_t = st.time_input("Jam Selesai/Cek", value=old_end.time())
                new_end_dt = datetime.combine(new_end_d, new_end_t)
            
            # Preview Durasi Baru
            preview_dur, _ = calculate_duration(new_start_dt, new_end_dt)
            st.caption(f"📅 Kalkulasi Durasi Baru: **{preview_dur}**")

            st.markdown("---")
            st.markdown("##### 📝 Update Data")

            # 2. EDIT DATA LAINNYA
            c_A1, c_A2, c_A3 = st.columns(3)
            with c_A1:
                new_status = st.selectbox("Update Status", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], index=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"].index(sel_row['Status']))
            with c_A2:
                # Logic Last Price
                val_price = float(sel_row['Last/Exit'])
                is_disabled = False
                if new_status in ["🚀 Hit TP", "⚠️ Hit SL"]: is_disabled = True
                new_price = st.number_input("Update Harga Akhir", value=val_price, format="%.4f", disabled=is_disabled)
            with c_A3:
                new_fee = st.number_input("Update Real Fee ($)", value=float(sel_row['Fee']), step=0.1)

            c_B1, c_B2 = st.columns(2)
            with c_B1: new_margin = st.number_input("Update Margin", value=float(sel_row['Margin']))
            with c_B2: new_entry = st.number_input("Update Avg Entry", value=float(sel_row['Entry']), format="%.4f")
            
            delete_trade = st.checkbox("🗑️ Hapus Trade Ini")

            if st.form_submit_button("💾 SIMPAN SEMUA PERUBAHAN", type="primary", use_container_width=True):
                if delete_trade:
                    st.session_state['portfolio'].pop(sel_index)
                    st.rerun()
                else:
                    # Update Logic
                    updated_data = process_trade_logic(
                        sel_row['ID'], 
                        new_start_dt, new_end_dt, # Kirim Waktu Baru
                        sel_row['Pair/Coin'], new_status, sel_row['Mode'], total_equity, sel_row['Arah'], 
                        new_margin, sel_row['Lev'], new_entry, new_price, 
                        float(sel_row['TP']), float(sel_row['SL']), 
                        new_fee, False
                    )
                    st.session_state['portfolio'][sel_index] = updated_data
                    st.rerun()

    # --- D. EXPORT ---
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export = df.drop(columns=["_float_val", "_real_val", "_is_running"])
        # Pastikan kolom datetime bisa dibaca excel
        df_export['Start Time'] = df_export['Start Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_export['End Time'] = df_export['End Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_export.to_excel(writer, index=False, sheet_name='Journal')
        
    st.download_button("📥 Download Excel Laporan (.xlsx)", buffer.getvalue(), f"Journal_{datetime.now().strftime('%Y%m%d')}.xlsx")

else:
    st.info("👋 Belum ada data. Input trade di Sidebar.")
