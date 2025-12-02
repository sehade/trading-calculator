import streamlit as st
import pandas as pd
from datetime import datetime
import io
import uuid # ID Unik

# ==========================================
# 1. KONFIGURASI TAMPILAN & CSS V4
# ==========================================
st.set_page_config(
    page_title="Pro Live Journal V4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk Indikator PnL Berwarna
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    
    /* Style Kartu Statistik */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #41424C;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
    }
    
    /* Tombol Tambah */
    div.stButton > button:first-child {
        background-color: #00CC96;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem;
        width: 100%;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #00a87d;
        transform: scale(1.02);
    }
    
    /* PnL Coloring Classes (Digunakan di logic dataframe styling jika support, 
       tapi streamil data_editor belum support row styling full, 
       jadi kita mainkan di text format) */
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SEMENTARA
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# ==========================================
# 3. ENGINE PERHITUNGAN (BACKEND V4)
# ==========================================
def calculate_row(
    id_trade, timestamp, coin, status, margin_mode, total_equity, pos_type, 
    margin, lev, avg_entry, last_price, tp, sl, fee_pct, fund_rate, days
):
    # Validasi dasar
    if avg_entry <= 0: return None
    
    # 1. Hitung Size & Quantity
    pos_size = margin * lev
    qty = pos_size / avg_entry
    
    # 2. Hitung Fee (Estimasi)
    trade_fee = pos_size * (fee_pct / 100)
    fund_fee = pos_size * (fund_rate / 100) * days
    total_fee = trade_fee + fund_fee
    
    # 3. Hitung Likuidasi
    if margin_mode == "Isolated Margin":
        risk_capital = margin
    else: 
        # Cross: Equity - Fee
        risk_capital = total_equity - total_fee 
        
    buffer = risk_capital / qty if qty > 0 else 0
    
    if "Long" in pos_type:
        liq_price = max(0, avg_entry - buffer)
        
        # Hitung Unrealized PnL (Floating) berdasarkan Last Price
        # Rumus Long: (Harga Sekarang - Harga Rata2) * Qty
        unrealized_pnl = (last_price - avg_entry) * qty
        
    else: # Short
        liq_price = avg_entry + buffer
        
        # Hitung Unrealized PnL (Floating)
        # Rumus Short: (Harga Rata2 - Harga Sekarang) * Qty
        unrealized_pnl = (avg_entry - last_price) * qty

    # ROE % (Return on Equity)
    roe_pct = (unrealized_pnl / margin) * 100
    
    # PnL Bersih (Setelah dipotong fee estimasi jika di-close sekarang)
    net_pnl_est = unrealized_pnl - total_fee

    # 4. Format PnL String dengan Indikator (+/-)
    # Ini trik agar di tabel terlihat beda meski teks biasa
    if net_pnl_est >= 0:
        pnl_display = f"🟢 +{roe_pct:.1f}% (+${net_pnl_est:.2f})"
    else:
        pnl_display = f"🔴 {roe_pct:.1f}% (-${abs(net_pnl_est):.2f})"

    # RETURN DATA BARIS
    return {
        "ID": id_trade, 
        "Waktu": timestamp,
        "Pair/Coin": coin.upper(),
        "Status": status,
        "Arah": pos_type,
        "Mode": margin_mode,
        "Margin ($)": float(margin),
        "Lev (x)": int(lev),
        "Avg Entry": float(avg_entry),
        "Last Price": float(last_price), # Kolom Kunci Monitoring
        "TP": float(tp),
        "SL": float(sl),
        
        # Kolom Hasil Hitungan
        "Liq Price": float(liq_price),
        "Floating PnL": pnl_display, # Teks berwarna (emoji)
        "Raw PnL ($)": float(net_pnl_est), # Angka murni untuk statistik
        "Fee Est ($)": float(total_fee)
    }

# ==========================================
# 4. SIDEBAR (CREATE NEW TRADE)
# ==========================================
with st.sidebar:
    st.title("🎛️ Input Posisi Baru")
    
    # A. Global Settings
    st.caption("--- 1. Info Dompet ---")
    total_equity = st.number_input("Total Saldo Aset (USDT)", value=1000.0, step=100.0)
    margin_mode = st.selectbox("Mode Margin", ["Isolated Margin", "Cross Margin"])

    # B. Identitas
    st.caption("--- 2. Identitas Trade ---")
    coin_name = st.text_input("Nama Coin", value="BTC/USDT")
    trade_status = st.selectbox("Status Awal", ["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"])

    # C. Setup
    st.caption("--- 3. Setup Posisi ---")
    pos_type = st.radio("Arah", ["Long (Buy) 🟢", "Short (Sell) 🔴"], horizontal=True, label_visibility="collapsed")
    c1, c2 = st.columns(2)
    with c1: margin_input = st.number_input("Margin ($)", value=10.0, min_value=1.0)
    with c2: lev_input = st.number_input("Lev (x)", value=20, min_value=1)

    # D. Harga
    st.caption("--- 4. Harga ---")
    entry_input = st.number_input("Avg Entry Price", value=50000.0, format="%.6f", help="Harga rata-rata pembelian")
    
    # Input Last Price (Otomatis disamakan dengan Entry saat baru input)
    # Nanti user bisa update ini di tabel monitoring
    
    c3, c4 = st.columns(2)
    with c3: tp_input = st.number_input("Target (TP)", value=55000.0, format="%.6f")
    with c4: sl_input = st.number_input("Stop Loss (SL)", value=48000.0, format="%.6f")

    # E. Fee
    with st.expander("⚙️ Fee Settings"):
        fee_pct = st.number_input("Fee (%)", value=0.045, format="%.4f")
        fund_rate = st.number_input("Funding (%)", value=0.010, format="%.3f")
        days_hold = st.number_input("Hari", value=0)
    
    # Info Margin Aman
    safe_margin = total_equity * 0.01
    st.info(f"💡 Saran: Margin aman per trade (1%) = ${safe_margin:.2f}")

    st.markdown("---")
    
    # TOMBOL CREATE
    if st.button("➕ Mulai Tracking"):
        if entry_input > 0:
            # Saat create, Last Price dianggap sama dengan Entry (Belum gerak)
            new_id = str(uuid.uuid4())
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            res = calculate_row(
                new_id, now_str, coin_name, trade_status, margin_mode, total_equity, 
                pos_type, margin_input, lev_input, entry_input, entry_input, 
                tp_input, sl_input, fee_pct, fund_rate, days_hold
            )
            
            if res:
                st.session_state['portfolio'].append(res)
                st.toast("Posisi ditambahkan ke Monitor!", icon="✅")
        else:
            st.error("Entry Price wajib diisi!")

# ==========================================
# 5. DASHBOARD MONITORING (LIVE PNL)
# ==========================================
c_head1, c_head2 = st.columns([3, 1])
with c_head1:
    st.title("📊 Pro Live Monitor")
    st.caption(f"Saldo Aset: **${total_equity:,.2f}** | Update 'Last Price' di tabel untuk lihat PnL Real-time.")
with c_head2:
    st.metric("Mode Aktif", margin_mode)

st.markdown("---")

if len(st.session_state['portfolio']) > 0:
    
    df = pd.DataFrame(st.session_state['portfolio'])
    
    # --- A. TABEL MONITORING (CRUD) ---
    st.subheader("🔴🟢 Tabel Monitoring Real-Time")
    st.info("💡 **Cara Update PnL:** Ubah angka di kolom **'Last Price'** sesuai harga pasar sekarang. PnL akan otomatis berubah warna.")

    # Konfigurasi Kolom Editor
    column_config = {
        "ID": None, # Sembunyikan
        "Raw PnL ($)": None, # Sembunyikan (ini buat hitungan statistik aja)
        "Fee Est ($)": None, # Sembunyikan biar tabel gak penuh
        
        "Status": st.column_config.SelectboxColumn(
            "Status", options=["🟢 Running", "🚀 Hit TP", "⚠️ Hit SL", "🏁 Closed"], width="medium", required=True
        ),
        "Arah": st.column_config.SelectboxColumn(
            "Arah", options=["Long (Buy) 🟢", "Short (Sell) 🔴"], width="small", required=True
        ),
        "Last Price": st.column_config.NumberColumn(
            "Last Price (Live)", 
            format="%.4f", 
            help="Update harga ini untuk lihat Floating PnL",
            min_value=0.000001
        ),
        "Floating PnL": st.column_config.TextColumn(
            "Floating PnL (Est)",
            width="medium",
            disabled=True # Read Only (Hasil hitungan)
        ),
        "Margin ($)": st.column_config.NumberColumn("Margin", format="$%.2f"),
        "Avg Entry": st.column_config.NumberColumn("Avg Entry", format="%.4f"),
        "Liq Price": st.column_config.NumberColumn("Liq Price", format="%.4f", disabled=True),
    }

    # RENDER TABEL
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="monitor_editor"
    )

    # --- B. OTAK OTOMATIS (RE-CALCULATE) ---
    if not edited_df.equals(df):
        updated_data = edited_df.to_dict('records')
        recalculated_portfolio = []
        
        for row in updated_data:
            # Hitung ulang berdasarkan Last Price baru
            recalc = calculate_row(
                id_trade=row.get("ID"),
                timestamp=row.get("Waktu"),
                coin=row.get("Pair/Coin"),
                status=row.get("Status"),
                margin_mode=row.get("Mode"),
                total_equity=total_equity, 
                pos_type=row.get("Arah"),
                margin=row.get("Margin ($)"),
                lev=row.get("Lev (x)"),
                avg_entry=row.get("Avg Entry"),
                last_price=row.get("Last Price"), # Ini yang sering diedit user
                tp=row.get("TP"),
                sl=row.get("SL"),
                fee_pct=fee_pct, 
                fund_rate=fund_rate, 
                days=days_hold
            )
            if recalc:
                recalculated_portfolio.append(recalc)
        
        st.session_state['portfolio'] = recalculated_portfolio
        st.rerun()

    # --- C. STATISTIK AGREGAT ---
    st.markdown("---")
    st.subheader("📈 Kesehatan Portfolio")
    
    total_margin = edited_df['Margin ($)'].sum()
    total_unrealized_pnl = edited_df['Raw PnL ($)'].sum() # PnL Bersih Total
    est_real_balance = total_equity + total_unrealized_pnl
    
    # 1. Health Bar
    usage_pct = (total_margin / total_equity) * 100
    if usage_pct < 5: color, status_msg = "#00CC96", "AMAN"
    elif usage_pct < 20: color, status_msg = "#FFAA00", "MODERATE"
    else: color, status_msg = "#FF4B4B", "BAHAYA"
    
    st.markdown(f"""
        <div style="margin-bottom: 5px;">Indikator Margin: <b style="color:{color}">{status_msg}</b></div>
        <div style="background-color: #262730; border-radius: 5px; margin-bottom: 20px;">
            <div style="width: {min(usage_pct, 100)}%; background-color: {color}; height: 15px; border-radius: 5px;"></div>
        </div>
    """, unsafe_allow_html=True)

    # 2. Metrik Besar
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Margin Terpakai", f"${total_margin:,.2f}")
    
    # Logic Warna Total PnL
    pnl_delta_color = "normal" if total_unrealized_pnl >= 0 else "inverse"
    with m2: st.metric("Total Floating PnL", f"${total_unrealized_pnl:,.2f}", "Net Profit/Loss", delta_color=pnl_delta_color)
    
    with m3: st.metric("Estimasi Saldo Real", f"${est_real_balance:,.2f}", "Jika Close Semua")
    with m4: st.metric("Total Posisi", len(edited_df))

    # --- D. EXPORT EXCEL ---
    st.markdown("### 📥 Backup Data")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Kita drop kolom ID sebelum export agar rapi
        export_df = edited_df.drop(columns=["ID", "Raw PnL ($)"]) 
        export_df.to_excel(writer, index=False, sheet_name='Live Monitor')
        
    st.download_button(
        label="Download Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"Monitor_Trading_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👋 Belum ada posisi. Masukkan data di Sidebar untuk mulai monitoring.")
