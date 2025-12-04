import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import io
import uuid

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="Ultimate Trading Manager V11",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    
    /* Kartu Statistik */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
    }
    
    /* Form Edit Mobile Friendly */
    div[data-testid="stForm"] {
        background-color: #1c1e26;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #41424C;
    }
    
    /* Risk Alert Box */
    .risk-box {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 15px;
        font-size: 0.9em;
        line-height: 1.4;
    }
    .risk-safe { background-color: #1f3a2f; color: #00cc96; border: 1px solid #00cc96; }
    .risk-warning { background-color: #3a2e1f; color: #ffaa00; border: 1px solid #ffaa00; }
    .risk-danger { background-color: #3a1f1f; color: #ff4b4b; border: 1px solid #ff4b4b; }
    
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE (SESSION STATE)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. LOGIKA UTAMA (BACKEND V11)
# ==========================================
def calculate_duration(start_dt, end_dt):
    # Hitung selisih waktu
    diff = end_dt - start_dt
    total_seconds = diff.total_seconds()
    
    if total_seconds < 0: 
        return "Error (Negatif)", 0
        
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    
    return f"{days} Hari {hours} Jam", total_seconds

def process_trade_logic(
    id_trade, start_dt, end_dt, 
    coin, status, margin_mode, total_equity, pos_type, 
    margin, lev, avg_entry, manual_last_price, tp, sl, 
    fee_trading_dollar, fee_funding_dollar
):
    if avg_entry <= 0: return None
    
    # 1. Hitung Durasi (Time Engine)
    duration_str, _ = calculate_duration(start_dt, end_dt)
    
    # 2. Tentukan Last Price (Status Engine)
    final_price = manual_last_price
    if status == "🚀 Hit TP": final_price = tp
    elif status == "⚠️ Hit SL": final_price = sl
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
    
    # 5. Hitung PnL (Financial Engine)
    if "Long" in pos_type:
        pnl_raw = (final_price - avg_entry) * qty
    else: # Short
        pnl_raw = (avg_entry - final_price) * qty
        
    pnl_net = pnl_raw - total_fee
    roe_pct = (pnl_raw / margin) * 100 

    # 6. Format Tampilan Warna
    pnl_str = f"{roe_pct:.1f}% (${pnl_net:.2f})"
    pnl_display = f"🟢 +{pnl_str}" if pnl_net >= 0 else f"🔴 {pnl_str}"

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
    risk_capital = margin if margin_mode == "Isolated Margin" else (total_equity - total_fee)
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, avg_entry - buffer)
    else:
        liq_price = avg_entry + buffer

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
        "TP": float(tp),
        "SL": float(sl),
        
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
# 4. SIDEBAR (CREATE NEW TRADE)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Trade Baru")
    
    # A. GLOBAL SETTINGS
    st.caption("--- Info Akun ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # --- FITUR: RISK ASSISTANT (V11) ---
    st.markdown("---")
    st.caption("🛡️ Risk Assistant")
    
    # Hitung batas aman
    safe_05 = total_equity * 0.005
    safe_10 = total_equity * 0.01
    
    st.markdown(f"""
    <div style="font-size:0.85em; color:#aaa;">
        Saran Margin Aman (0.5% - 1%):<br>
        <b>${safe_05:.2f} - ${safe_10:.2f}</b> per trade.
    </div>
    """, unsafe_allow_html=True)
    # -----------------------------------

    # B. WAKTU (TIME TRACKER)
    st.caption("--- Waktu Buka Posisi ---")
    c_t1, c_t2 = st.columns(2)
    with c_t1: start_d = st.date_input("Tanggal", value="today")
    with c_t2: start_t = st.time_input("Jam", value="now")
    start_dt_combine = datetime.combine(start_d, start_t)

    # C. IDENTITAS
    st.caption("--- Identitas Trade ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    status_input = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])
    
    # D. SETUP POSISI (DENGAN ALERT RISK)
    st.caption("--- Setup Posisi ---")
    pos_type = st.radio("Arah", ["Long 🟢", "Short 🔴"], horizontal=True)
    c1, c2 = st.columns(2)
    margin_in = c1.number_input("Margin ($)", value=10.0, step=1.0)
    lev_in = c2.number_input("Lev (x)", value=20)
    
    # >>> LOGIKA ALERT RISK <<<
    if margin_in > safe_10:
        st.markdown(f"<div class='risk-box risk-danger'>⚠️ <b>BAHAYA!</b> Margin > 1% Saldo (${safe_10:.2f}). Risiko tinggi!</div>", unsafe_allow_html=True)
    elif margin_in > safe_05:
        st.markdown(f"<div class='risk-box risk-warning'>⚠️ <b>Hati-hati.</b> Margin > 0.5% Saldo.</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='risk-box risk-safe'>✅ <b>Aman.</b> Margin dalam batas wajar.</div>", unsafe_allow_html=True)
    # -------------------------

    entry_in = st.number_input("Avg Entry", value=50000.0, format="%.4f")
    
    # Logic Input Harga Akhir
    last_price_label = "Current Price" if status_input == "🟢 Running" else "Exit Price"
    # Jika TP/SL, nanti otomatis. Jika Running/Closed, user input.
    last_price_in = st.number_input(f"{last_price_label}", value=50000.0, format="%.4f")
    
    c3, c4 = st.columns(2)
    tp_in = c3.number_input("TP", value=55000.0, format="%.4f")
    sl_in = c4.number_input("SL", value=48000.0, format="%.4f")

    # E. FEE (FEE LOCKING LOGIC)
    st.caption("--- Biaya (Fee) ---")
    
    disable_fee = (status_input == "🟢 Running")
    if disable_fee:
        st.info("ℹ️ Status Running: Fee dikunci 0. Input saat Close nanti.")
        in_trade_fee, in_fund_fee = 0.0, 0.0
    else:
        c_f1, c_f2 = st.columns(2)
        in_trade_fee = c_f1.number_input("Trading Fee ($)", value=0.0, step=0.1)
        in_fund_fee = c_f2.number_input("Funding Fee ($)", value=0.0, step=0.1)
    
    st.markdown("---")
    if st.button("➕ Tambah Trade"):
        if entry_in > 0:
            # End time default = Sekarang
            end_dt_now = datetime.now()
            
            res = process_trade_logic(
                str(uuid.uuid4()), start_dt_combine, end_dt_now,
                coin_name, status_input, margin_mode, total_equity, 
                pos_type, margin_in, lev_in, entry_in, last_price_in, tp_in, sl_in, 
                in_trade_fee, in_fund_fee
            )
            st.session_state['portfolio'].append(res)
            st.toast("Trade Ditambahkan!", icon="✅")
        else:
            st.error("Entry Price wajib diisi!")

# ==========================================
# 5. DASHBOARD UTAMA
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
c_head1.title("💎 Ultimate Trading Manager")
c_head2.metric("Saldo Aset", f"${total_equity:,.2f}")
st.markdown("---")

if len(st.session_state['portfolio']) > 0:
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # A. STATISTIK KEUANGAN
    st.subheader("📈 Ringkasan Portofolio")
    
    total_margin = df[df['_is_running'] == True]['Margin'].sum()
    total_floating = df['_float_val'].sum()
    total_realized = df['_real_val'].sum()
    total_fees_paid = df['Total Fee ($)'].sum()
    
    curr_bal = total_equity + total_realized
    
    # Health Bar Logic
    usage_pct = (total_margin / curr_bal) * 100 if curr_bal > 0 else 0
    if usage_pct < 5: color, msg = "#00CC96", "AMAN"
    elif usage_pct < 20: color, msg = "#FFAA00", "MODERATE"
    else: color, msg = "#FF4B4B", "BAHAYA"
    
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
    m4.metric("Total Fee Paid", f"-${total_fees_paid:,.2f}")

    # B. TABEL MONITORING LENGKAP
    st.markdown("---")
    st.subheader("📋 Tabel Monitoring")
    
    # Format Waktu
    df['Waktu Buka'] = df['Start Time'].dt.strftime('%d-%b %H:%M')
    
    display_cols = [
        "Waktu Buka", "Durasi", "Pair/Coin", "Status", "Arah", 
        "Margin", "Entry", "Last/Exit", 
        "Trading Fee ($)", "Funding Fee ($)", 
        "Floating PnL", "Realized PnL"
    ]
    
    st.dataframe(
        df[display_cols].style.format({
            "Margin": "${:,.2f}",
            "Entry": "{:,.4f}",
            "Last/Exit": "{:,.4f}",
            "Trading Fee ($)": "${:,.2f}",
            "Funding Fee ($)": "${:,.2f}",
        }), 
        use_container_width=True, 
        height=300
    )

    # C. FORM EDIT (MOBILE FRIENDLY)
    st.markdown("---")
    st.subheader("✏️ Edit & Update Trade")
    
    trade_options = df.apply(lambda x: f"{x['Pair/Coin']} ({x['Status']}) - {x['Durasi']}", axis=1).tolist()
    selected_option = st.selectbox("Pilih Trade:", trade_options)
    
    if selected_option:
        idx = trade_options.index(selected_option)
        row = df.iloc[idx]
        
        # 1. Update Status & Waktu
        c_up1, c_up2 = st.columns(2)
        new_status = c_up1.selectbox("Update Status", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], index=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"].index(row['Status']))
        
        # Logika Kunci Fee
        is_fee_locked = (new_status == "🟢 Running")
        
        with st.form("edit_form"):
            st.info(f"Mengedit: **{row['Pair/Coin']}**")
            
            # Waktu
            st.markdown("##### ⏱️ Waktu & Durasi")
            c_t1, c_t2 = st.columns(2)
            
            # Start Time
            ns_d = c_t1.date_input("Tanggal Mulai", row['Start Time'].date())
            ns_t = c_t1.time_input("Jam Mulai", row['Start Time'].time())
            new_start = datetime.combine(ns_d, ns_t)
            
            # End Time
            ne_d = c_t2.date_input("Tanggal Akhir/Cek", row['End Time'].date())
            ne_t = c_t2.time_input("Jam Akhir/Cek", row['End Time'].time())
            new_end = datetime.combine(ne_d, ne_t)
            
            # Preview Durasi
            prev_dur, _ = calculate_duration(new_start, new_end)
            st.caption(f"Durasi Baru: {prev_dur}")
            
            st.markdown("##### 💵 Harga & Margin")
            c_p1, c_p2, c_p3 = st.columns(3)
            
            # Logic Lock Price
            price_dis = new_status in ["🚀 Hit TP", "⚠️ Hit SL"]
            new_price = c_p1.number_input("Last/Exit Price", value=float(row['Last/Exit']), format="%.4f", disabled=price_dis)
            new_entry = c_p2.number_input("Avg Entry", value=float(row['Entry']), format="%.4f")
            new_margin = c_p3.number_input("Margin ($)", value=float(row['Margin']))
            
            st.markdown("##### 💸 Fee Manual")
            c_f1, c_f2 = st.columns(2)
            v_t_fee = 0.0 if is_fee_locked else float(row['Trading Fee ($)'])
            v_f_fee = 0.0 if is_fee_locked else float(row['Funding Fee ($)'])
            
            new_trade_fee = c_f1.number_input("Trading Fee ($)", value=v_t_fee, step=0.1, disabled=is_fee_locked)
            new_fund_fee = c_f2.number_input("Funding Fee ($)", value=v_f_fee, step=0.1, disabled=is_fee_locked)
            
            st.markdown("##### 🎯 Target")
            c_x1, c_x2, c_x3 = st.columns(3)
            new_tp = c_x1.number_input("TP", value=float(row['TP']), format="%.4f")
            new_sl = c_x2.number_input("SL", value=float(row['SL']), format="%.4f")
            new_lev = c_x3.number_input("Lev", value=int(row['Lev']))
            
            do_delete = st.checkbox("🗑️ Hapus Trade Ini Permanen")
            
            if st.form_submit_button("💾 SIMPAN UPDATE", type="primary", use_container_width=True):
                if do_delete:
                    st.session_state['portfolio'].pop(idx)
                    st.rerun()
                else:
                    updated = process_trade_logic(
                        row['ID'], new_start, new_end, row['Pair/Coin'], new_status, row['Mode'], total_equity, row['Arah'],
                        new_margin, new_lev, new_entry, new_price, new_tp, new_sl, 
                        new_trade_fee, new_fund_fee
                    )
                    st.session_state['portfolio'][idx] = updated
                    st.rerun()

    # D. EXPORT
    st.markdown("---")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exp = df.drop(columns=["_float_val", "_real_val", "_is_running"])
        df_exp['Start Time'] = df_exp['Start Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_exp['End Time'] = df_exp['End Time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        df_exp.to_excel(writer, index=False, sheet_name='Journal')
    st.download_button("📥 Download Excel Laporan", buffer.getvalue(), f"Journal_{datetime.now().strftime('%Y%m%d')}.xlsx")

else:
    st.info("👋 Belum ada data. Input trade baru di Sidebar.")
