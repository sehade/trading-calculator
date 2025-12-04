import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import io
import uuid

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="Ultimate Trading Manager V14",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Kustom untuk Tampilan Profesional
st.markdown("""
<style>
    /* Latar Belakang Gelap Utama */
    .main { background-color: #0e1117; }
    
    /* Styling Kartu Statistik (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
    }
    
    /* Styling Form Edit agar terlihat jelas di HP */
    div[data-testid="stForm"] {
        background-color: #1c1e26;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #41424C;
        margin-top: 20px;
    }
    
    /* Risk Alert Box (Kotak Peringatan Risiko) */
    .risk-box {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 15px;
        font-size: 0.9em;
        border-left: 5px solid;
    }
    .risk-safe { 
        background-color: #1f3a2f; 
        color: #00cc96; 
        border-color: #00cc96; 
    }
    .risk-warning { 
        background-color: #3a2e1f; 
        color: #ffaa00; 
        border-color: #ffaa00; 
    }
    .risk-danger { 
        background-color: #3a1f1f; 
        color: #ff4b4b; 
        border-color: #ff4b4b; 
    }
    
    /* Font Judul */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE (SESSION STATE)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. LOGIKA BACKEND (THE BRAIN)
# ==========================================

# --- A. Smart Duration (Menghitung Waktu Nahan Floating) ---
def calculate_smart_duration(start_dt, end_dt):
    # Hitung selisih waktu
    diff = end_dt - start_dt
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 0: 
        return "Error (Waktu Mundur)", 0
    
    # Konversi ke Hari, Jam, Menit
    days = total_seconds // 86400
    rem_seconds = total_seconds % 86400
    hours = rem_seconds // 3600
    rem_seconds %= 3600
    minutes = rem_seconds // 60
    
    # Format Teks Dinamis
    parts = []
    if days > 0:
        parts.append(f"{days} Hari")
    if hours > 0:
        parts.append(f"{hours} Jam")
    if minutes > 0:
        parts.append(f"{minutes} Menit")
    
    if not parts:
        return "Baru Saja", total_seconds
        
    return " ".join(parts), total_seconds

# --- B. Proses Logika Utama (Calculator) ---
def process_trade_logic(
    id_trade, start_dt, end_dt, 
    coin, status, margin_mode, total_equity, pos_type, 
    margin, lev, avg_entry, manual_last_price, tp, sl, 
    fee_trading_dollar, fee_funding_dollar
):
    # Validasi Pembagian Nol
    if avg_entry <= 0: return None
    
    # 1. Hitung Durasi (Time Engine)
    duration_str, _ = calculate_smart_duration(start_dt, end_dt)
    
    # 2. Tentukan Last Price (Status Engine)
    final_price = manual_last_price
    if status == "🚀 Hit TP": 
        final_price = tp # Kunci ke TP
    elif status == "⚠️ Hit SL": 
        final_price = sl # Kunci ke SL
    # Jika Running/Closed, pakai manual_last_price
        
    is_running = (status == "🟢 Running")

    # 3. Hitung Size & Qty
    pos_size = margin * lev
    qty = pos_size / avg_entry
    
    # 4. Logika Fee (Locking Engine)
    # Jika Running, Fee dipaksa 0 karena belum realisasi
    if is_running:
        real_trade_fee = 0.0
        real_fund_fee = 0.0
    else:
        real_trade_fee = fee_trading_dollar
        real_fund_fee = fee_funding_dollar
        
    total_fee = real_trade_fee + real_fund_fee
    
    # 5. Hitung PnL (Profit & Loss)
    if "Long" in pos_type:
        pnl_raw = (final_price - avg_entry) * qty
    else: # Short
        pnl_raw = (avg_entry - final_price) * qty
        
    pnl_net = pnl_raw - total_fee
    roe_pct = (pnl_raw / margin) * 100 

    # 6. Format Tampilan Warna PnL
    pnl_str = f"{roe_pct:.1f}% (${pnl_net:.2f})"
    if pnl_net >= 0:
        pnl_display = f"🟢 +{pnl_str}" 
    else:
        pnl_display = f"🔴 {pnl_str}"

    # 7. Split PnL (Floating vs Realized)
    if is_running:
        floating_display = pnl_display
        floating_val = pnl_net
        realized_display = "-"
        realized_val = 0.0
    else:
        floating_display = "-"
        floating_val = 0.0
        realized_display = pnl_display
        realized_val = pnl_net

    # 8. Hitung Likuidasi (Safety Engine)
    if margin_mode == "Isolated Margin":
        risk_capital = margin 
    else:
        risk_capital = total_equity - total_fee
        
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, avg_entry - buffer)
    else:
        liq_price = avg_entry + buffer

    # 9. Hitung Persentase TP/SL (Fitur Baru V12/V13)
    if "Long" in pos_type:
        tp_pct = ((tp - avg_entry) / avg_entry) * 100
        sl_pct = ((sl - avg_entry) / avg_entry) * 100
    else:
        tp_pct = ((avg_entry - tp) / avg_entry) * 100
        sl_pct = ((avg_entry - sl) / avg_entry) * 100

    tp_display = f"${tp:,.4f} ({tp_pct:+.1f}%)"
    sl_display = f"${sl:,.4f} ({sl_pct:+.1f}%)"

    # RETURN DATA COMPLETE
    return {
        "ID": id_trade,
        
        # Waktu
        "Start Time": start_dt,
        "End Time": end_dt,
        "Durasi": duration_str,
        
        # Identitas
        "Pair/Coin": coin.upper(),
        "Status": status,
        "Arah": pos_type,
        "Mode": margin_mode,
        
        # Teknis
        "Margin": float(margin),
        "Lev": int(lev),
        "Entry": float(avg_entry),
        "Last/Exit": float(final_price),
        
        # TP/SL dengan Persentase
        "TP_Val": float(tp), 
        "SL_Val": float(sl),
        "TP Display": tp_display,
        "SL Display": sl_display,
        
        "Liq Price": float(liq_price),
        
        # Fee Terpisah
        "Trading Fee ($)": float(real_trade_fee),
        "Funding Fee ($)": float(real_fund_fee),
        "Total Fee ($)": float(total_fee),
        
        # PnL Terpisah
        "Floating PnL": floating_display,
        "Realized PnL": realized_display,
        
        # Hidden Values (untuk statistik)
        "_float_val": floating_val,
        "_real_val": realized_val,
        "_is_running": is_running,
    }

# ==========================================
# 4. SIDEBAR (INPUT & RISK MANAGEMENT)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Trade Baru")
    
    # A. GLOBAL SETTINGS
    st.caption("--- Info Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # --- FITUR: SMART RISK ASSISTANT (Wajib Ada) ---
    st.markdown("---")
    st.markdown("### 🛡️ Risk Assistant")
    
    # Hitung batas aman 0.5% - 1%
    safe_min = total_equity * 0.005 # 0.5%
    safe_max = total_equity * 0.01  # 1.0%
    
    st.info(f"💡 **Saran Margin Aman (0.5% - 1%):**\n ${safe_min:.2f} — ${safe_max:.2f}")
    # --------------------------------------------------

    # B. WAKTU (TIME TRACKER)
    st.caption("--- Waktu Buka Posisi ---")
    c_t1, c_t2 = st.columns(2)
    with c_t1: 
        start_d = st.date_input("Tanggal Buka", value="today")
    with c_t2: 
        start_t = st.time_input("Jam Buka", value="now", step=60) # Step 60 = Presisi menit
    
    start_dt_combine = datetime.combine(start_d, start_t)

    # C. IDENTITAS
    st.caption("--- Identitas Trade ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    status_input = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])
    
    # Logic Waktu Tutup (Sembunyi jika Running)
    if status_input == "🟢 Running":
        end_dt_combine = datetime.now() # Real-time
        st.info("🕒 Posisi Running: Waktu Tutup = Sekarang")
    else:
        c_t3, c_t4 = st.columns(2)
        end_d = c_t3.date_input("Tanggal Tutup", value="today")
        end_t = c_t4.time_input("Jam Tutup", value="now", step=60)
        end_dt_combine = datetime.combine(end_d, end_t)

    # D. SETUP POSISI (DENGAN ALERT RISK MERAH/HIJAU)
    st.caption("--- Setup Posisi ---")
    pos_type = st.radio("Arah", ["Long 🟢", "Short 🔴"], horizontal=True)
    
    c1, c2 = st.columns(2)
    margin_in = c1.number_input("Margin ($)", value=10.0, step=1.0)
    lev_in = c2.number_input("Lev (x)", value=20)
    
    # >>> LOGIKA ALERT MARGIN VISUAL <<<
    if margin_in > safe_max:
        st.markdown(
            f"<div class='risk-box risk-danger'>🚨 <b>OVERTRADE WARNING!</b><br>"
            f"Margin Anda (${margin_in}) melebihi 1% saldo (${safe_max:.2f}).<br>"
            f"Risiko kebangkrutan tinggi!</div>", 
            unsafe_allow_html=True
        )
    elif margin_in > safe_min:
        st.markdown(
            f"<div class='risk-box risk-warning'>⚠️ <b>MODERATE RISK</b><br>"
            f"Margin > 0.5%. Masih batas wajar tapi hati-hati.</div>", 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div class='risk-box risk-safe'>✅ <b>SAFE ZONE</b><br>"
            f"Margin sangat aman (< 0.5%).</div>", 
            unsafe_allow_html=True
        )
    # ----------------------------------
    
    entry_in = st.number_input("Avg Entry", value=50000.0, format="%.4f")
    
    # Logic Input Harga Akhir
    last_price_label = "Current Price" if status_input == "🟢 Running" else "Exit Price"
    
    # Jika TP/SL, nanti otomatis. Jika Running/Closed, user input.
    if status_input in ["🟢 Running", "🏁 Closed"]:
        last_price_in = st.number_input(f"{last_price_label}", value=50000.0, format="%.4f")
    else:
        last_price_in = entry_in 
    
    c3, c4 = st.columns(2)
    tp_in = c3.number_input("TP", value=55000.0, format="%.4f")
    sl_in = c4.number_input("SL", value=48000.0, format="%.4f")

    # E. FEE (FEE LOCKING LOGIC)
    st.caption("--- Biaya (Fee) ---")
    
    disable_fee = (status_input == "🟢 Running")
    if disable_fee:
        st.info("ℹ️ Fee dikunci 0 saat Running.")
        in_trade_fee, in_fund_fee = 0.0, 0.0
    else:
        c_f1, c_f2 = st.columns(2)
        in_trade_fee = c_f1.number_input("Trading Fee ($)", value=0.0, step=0.1)
        in_fund_fee = c_f2.number_input("Funding Fee ($)", value=0.0, step=0.1)
    
    st.markdown("---")
    
    if st.button("➕ Tambah Trade"):
        if entry_in > 0:
            res = process_trade_logic(
                str(uuid.uuid4()), start_dt_combine, end_dt_combine,
                coin_name, status_input, margin_mode, total_equity, 
                pos_type, margin_in, lev_in, entry_in, last_price_in, tp_in, sl_in, 
                in_trade_fee, in_fund_fee
            )
            st.session_state['portfolio'].append(res)
            st.toast("Trade Berhasil Disimpan!", icon="✅")
        else:
            st.error("Entry Price wajib diisi!")

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
c_head1.title("💎 Ultimate Trading V14")
c_head2.metric("Saldo Aset", f"${total_equity:,.2f}")
st.markdown("---")

if len(st.session_state['portfolio']) > 0:
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # --- A. STATISTIK KEUANGAN & HEALTH BAR ---
    st.subheader("📈 Ringkasan Portofolio")
    
    total_margin = df[df['_is_running'] == True]['Margin'].sum()
    total_floating = df['_float_val'].sum()
    total_realized = df['_real_val'].sum()
    total_fees_usd = df['Total Fee ($)'].sum()
    
    curr_bal = total_equity + total_realized
    
    # Health Bar Logic
    usage_pct = (total_margin / curr_bal) * 100 if curr_bal > 0 else 0
    
    # Penentuan Warna Health Bar
    if usage_pct < 5: 
        color, msg = "#00CC96", "AMAN"
    elif usage_pct < 20: 
        color, msg = "#FFAA00", "MODERATE"
    else: 
        color, msg = "#FF4B4B", "BAHAYA"
    
    st.markdown(f"""
        <div style="margin-bottom:5px;">Health Bar: <b style="color:{color}">{msg}</b> ({usage_pct:.1f}%)</div>
        <div style="background:#262730; height:10px; border-radius:5px; width:100%; margin-bottom:15px;">
            <div style="background:{color}; width:{min(usage_pct, 100)}%; height:100%; border-radius:5px;"></div>
        </div>
    """, unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Floating PnL", f"${total_floating:,.2f}", delta_color="normal" if total_floating>=0 else "inverse")
    m2.metric("Kumulatif PnL", f"${total_realized:,.2f}", delta_color="normal" if total_realized>=0 else "inverse")
    m3.metric("Saldo Real", f"${curr_bal:,.2f}")
    m4.metric("Total Fee Paid", f"-${total_fees_usd:,.2f}")

    # --- B. TABEL MONITORING (LENGKAP V12/13/14) ---
    st.markdown("---")
    st.subheader("📋 Tabel Monitoring")
    
    # Format Tampilan Waktu
    df['Buka'] = df['Start Time'].dt.strftime('%d/%m %H:%M')
    df['Tutup'] = df['End Time'].dt.strftime('%d/%m %H:%M')
    
    # Kolom Pilihan Lengkap
    display_cols = [
        "Pair/Coin", "Status", "Arah", 
        "Buka", "Tutup", "Durasi", 
        "Margin", "Entry", "TP Display", "SL Display", 
        "Liq Price", "Last/Exit", "Floating PnL", "Realized PnL"
    ]
    
    st.dataframe(
        df[display_cols].style.format({
            "Margin": "${:,.2f}",
            "Entry": "{:,.4f}",
            "Last/Exit": "{:,.4f}",
            "Liq Price": "{:,.4f}",
        }), 
        use_container_width=True, 
        height=300
    )

    # --- C. FORM EDIT (MOBILE FRIENDLY & FEE MANUAL) ---
    st.markdown("---")
    st.subheader("✏️ Edit Trade")
    
    trade_options = df.apply(lambda x: f"{x['Pair/Coin']} ({x['Status']})", axis=1).tolist()
    selected_option = st.selectbox("Pilih Trade:", trade_options)
    
    if selected_option:
        idx = trade_options.index(selected_option)
        row = df.iloc[idx]
        
        # STATUS EDIT
        new_status = st.selectbox(
            "Update Status", 
            ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], 
            index=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"].index(row['Status'])
        )
        is_fee_locked = (new_status == "🟢 Running")
        
        with st.form("edit_form"):
            st.info(f"Edit: **{row['Pair/Coin']}**")
            
            # 1. WAKTU (UPDATE DINAMIS)
            st.markdown("##### ⏱️ Waktu")
            c_t1, c_t2 = st.columns(2)
            
            # Edit Start
            ns_d = c_t1.date_input("Tgl Buka", row['Start Time'].date())
            ns_t = c_t1.time_input("Jam Buka", row['Start Time'].time(), step=60)
            new_start = datetime.combine(ns_d, ns_t)
            
            # Edit End (Tergantung Status)
            if new_status == "🟢 Running":
                st.caption("Status Running: Waktu Tutup otomatis 'Sekarang' (Realtime).")
                new_end = datetime.now()
            else:
                ne_d = c_t2.date_input("Tgl Tutup", row['End Time'].date())
                ne_t = c_t2.time_input("Jam Tutup", row['End Time'].time(), step=60)
                new_end = datetime.combine(ne_d, ne_t)
            
            # Preview Durasi
            prev_dur, _ = calculate_smart_duration(new_start, new_end)
            st.caption(f"Durasi Baru: {prev_dur}")
            
            # 2. HARGA
            st.markdown("##### 💵 Harga & Teknis")
            c_p1, c_p2, c_p3 = st.columns(3)
            
            # Logic Lock Price saat edit
            price_dis = new_status in ["🚀 Hit TP", "⚠️ Hit SL"]
            new_price = c_p1.number_input("Last/Exit Price", value=float(row['Last/Exit']), format="%.4f", disabled=price_dis)
            new_entry = c_p2.number_input("Avg Entry", value=float(row['Entry']), format="%.4f")
            new_margin = c_p3.number_input("Margin ($)", value=float(row['Margin']))
            
            # 3. FEE (Edit Manual)
            st.markdown("##### 💸 Fee")
            c_f1, c_f2 = st.columns(2)
            v_t_fee = 0.0 if is_fee_locked else float(row['Trading Fee ($)'])
            v_f_fee = 0.0 if is_fee_locked else float(row['Funding Fee ($)'])
            
            new_trade_fee = c_f1.number_input("Trading Fee", value=v_t_fee, step=0.1, disabled=is_fee_locked)
            new_fund_fee = c_f2.number_input("Funding Fee", value=v_f_fee, step=0.1, disabled=is_fee_locked)
            
            # 4. TP SL
            st.markdown("##### 🎯 Target")
            c_x1, c_x2, c_x3 = st.columns(3)
            new_tp = c_x1.number_input("TP", value=float(row['TP_Val']), format="%.4f")
            new_sl = c_x2.number_input("SL", value=float(row['SL_Val']), format="%.4f")
            new_lev = c_x3.number_input("Lev", value=int(row['Lev']))
            
            do_delete = st.checkbox("Hapus Trade")
            
            if st.form_submit_button("Simpan Perubahan", type="primary"):
                if do_delete:
                    st.session_state['portfolio'].pop(idx)
                else:
                    updated = process_trade_logic(
                        row['ID'], new_start, new_end, row['Pair/Coin'], new_status, row['Mode'], total_equity, row['Arah'],
                        new_margin, new_lev, new_entry, new_price, new_tp, new_sl, 
                        new_trade_fee, new_fund_fee
                    )
                    st.session_state['portfolio'][idx] = updated
                st.rerun()

    # --- D. EXPORT EXCEL ---
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exp = df.drop(columns=["_float_val", "_real_val", "_is_running"])
        # Format tanggal untuk excel
        df_exp['Start Time'] = df_exp['Start Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_exp['End Time'] = df_exp['End Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_exp.to_excel(writer, index=False, sheet_name='Journal')
    st.download_button("📥 Download Excel Laporan", buffer.getvalue(), f"Journal_{datetime.now().strftime('%Y%m%d')}.xlsx")

else:
    st.info("👋 Belum ada data. Input trade baru di Sidebar.")
