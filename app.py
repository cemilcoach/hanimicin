import time
import hashlib
import streamlit as st
import requests
import re

# =============================
# AYARLAR
# =============================
API_KEY = st.secrets.get("FIVESIM_TOKEN", "TOKEN_YOK")
PASSWORD_HASH = st.secrets.get("PANEL_PASSWORD_HASH", "")

BASE_URL = "https://5sim.net/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# Sabitler
COUNTRY = "england"
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900 

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS (EKRAN KAYMASI ENGELLİ)
# =============================
st.markdown("""
    <style>
        /* Header ve Footer Kaymasını Önleyen Boşluklar */
        .block-container {
            padding-top: 3rem !important; 
            padding-bottom: 10rem !important;
        }
        
        /* Butonları İyileştir */
        .stButton button {
            height: 3.5rem !important;
            width: 100% !important;
            font-size: 16px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Kod Kutusu Yazı Boyutu */
        .stCode { font-size: 1.3rem !important; }
        
        div[data-testid="stVerticalBlock"] {gap: 1rem;}
    </style>
""", unsafe_allow_html=True)

# =============================
# GİRİŞ
# =============================
def check_login():
    if "authenticated" not in st.session_state: st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.warning("🔐 Panel Giriş")
        with st.form("login"):
            pwd = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap"):
                if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
                    st.session_state.authenticated = True
                    st.rerun()
                else: st.error("Hatalı Şifre")
        return False
    return True

if not check_login(): st.stop()

# =============================
# STATE
# =============================
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time", "raw_data"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# FONKSİYONLAR
# =============================
def buy_number():
    try:
        url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if "id" in data:
            full = data["phone"]
            local = full[3:] if full.startswith("+44") else (full[2:] if full.startswith("44") else full)
            
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = full
            st.session_state.phone_local = local
            st.session_state.sms_code = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
            st.session_state.raw_data = None
        else:
            st.error(f"Hata: {data}")
    except Exception as e: st.error(f"Bağlantı: {e}")

def check_sms():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/check/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            st.session_state.raw_data = data # Debug için kaydet
            st.session_state.status = data.get("status")
            
            sms_list = data.get("sms", [])
            if sms_list:
                # 1. YÖNTEM: Direkt Code Alanı
                code = sms_list[0].get("code")
                
                # 2. YÖNTEM: Text İçinden Regex ile Bulma (Yedek)
                if not code:
                    text = sms_list[0].get("text", "")
                    match = re.search(r'\b\d{4,8}\b', text)
                    if match:
                        code = match.group(0)
                
                if code:
                    st.session_state.sms_code = code
                    st.session_state.start_time = None
    except: pass

def cancel_order():
    if st.session_state.order_id:
        requests.get(f"{BASE_URL}/user/cancel/{st.session_state.order_id}", headers=HEADERS)
        reset_state()

def ban_order():
    if st.session_state.order_id:
        requests.get(f"{BASE_URL}/user/ban/{st.session_state.order_id}", headers=HEADERS)
        reset_state()

def reset_state():
    for key in ["order_id", "phone_full", "phone_local", "sms_code", "start_time", "status", "raw_data"]:
        st.session_state[key] = None

# =============================
# ARAYÜZ
# =============================

if not st.session_state.order_id:
    # --- NUMARA YOKSA ---
    st.info("Sistem Hazır.")
    if st.button("🚀 YENİ NUMARA AL (Uber)", type="primary"):
        buy_number()
        st.rerun()

else:
    # --- NUMARA VARSA ---
    
    # 1. Numaralar
    st.write("🌍 **Tam Numara (+44)**")
    st.code(st.session_state.phone_full, language="text")

    st.write("🏠 **Sadece Numara (KODSUZ)**")
    st.code(st.session_state.phone_local, language="text")

    st.divider()

    # 2. SMS Alanı
    st.write("📩 **SMS Kodu**")
    
    if st.session_state.sms_code:
        st.success("KOD GELDİ!")
        st.code(st.session_state.sms_code, language="text")
    else:
        # Bekleme Modu
        st.code(".....", language="text")
        
        # Manuel Kontrol Butonu (Hayat Kurtarıcı)
        col_check1, col_check2 = st.columns([3, 1])
        with col_check2:
            if st.button("🔄", help="Manuel Kontrol Et"):
                check_sms()
                st.rerun()
        
        # Süre ve Otomatik Yenileme
        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            rem = MAX_WAIT_SECONDS - elapsed
            
            if rem > 0:
                m, s = divmod(rem, 60)
                with col_check1:
                    st.caption(f"⏳ Bekleniyor... {m}:{s:02d}")
                
                # Otomatik Kontrol
                check_sms()
                if not st.session_state.sms_code:
                    time.sleep(3)
                    st.rerun()
            else:
                st.error("Süre Doldu.")

    st.divider()

    # 3. Aksiyon Butonları
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚫 Banla", use_container_width=True):
            ban_order()
            st.rerun()
    with c2:
        if st.button("❌ İptal", type="primary", use_container_width=True):
            cancel_order()
            st.rerun()

    # DEBUG ALANI (Gizli)
    # Eğer kod gelmiyorsa burayı açıp bakabilirsin
    with st.expander("🛠 Sorun mu var? (Ham Veri)"):
        st.json(st.session_state.raw_data)

    # Alt Boşluk
    st.write("\n" * 10)
