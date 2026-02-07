import time
import hashlib
import streamlit as st
import requests

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

COUNTRY = "england"
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900 

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS (HEADER KAYMASI ÇÖZÜMÜ)
# =============================
st.markdown("""
    <style>
        /* SORUNUN ÇÖZÜMÜ BURADA: */
        /* Üst boşluğu (padding-top) 5rem yaparak header altına girmeyi engelledik */
        .block-container {
            padding-top: 5rem !important; 
            padding-bottom: 5rem !important;
        }
        
        /* Buton Tasarımları */
        .stButton button {
            height: 3.5rem !important;
            width: 100% !important;
            font-size: 18px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.1);
        }
        
        div[data-testid="stVerticalBlock"] {gap: 1rem;}
        
        /* Şifre ekranını ortala */
        div[data-testid="stForm"] {border: none;}
    </style>
""", unsafe_allow_html=True)

# =============================
# GÜVENLİ GİRİŞ (URL AÇIĞI KAPATILDI)
# =============================
def check_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.warning("🔐 Güvenli Giriş")
        # Form kullanarak Enter tuşuyla girişi sağla
        with st.form("login_form"):
            pwd = st.text_input("Şifre", type="password")
            submitted = st.form_submit_button("Giriş Yap")
            
            if submitted:
                if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Hatalı şifre")
        return False
    return True

if not check_login(): st.stop()

# =============================
# FONKSİYONLAR
# =============================
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time"]:
    if key not in st.session_state:
        st.session_state[key] = None

def buy_number():
    try:
        url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if "id" in data:
            full = data["phone"]
            local = full
            if full.startswith("+44"): local = full[3:]
            elif full.startswith("44"): local = full[2:]
            
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = full
            st.session_state.phone_local = local
            st.session_state.sms_code = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
        else:
            st.error(f"Hata: {data}")
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
    for key in ["order_id", "phone_full", "phone_local", "sms_code", "start_time", "status"]:
        st.session_state[key] = None

def check_sms():
    if not st.session_state.order_id: return
    try:
        r = requests.get(f"{BASE_URL}/user/check/{st.session_state.order_id}", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            st.session_state.status = data.get("status")
            sms_list = data.get("sms", [])
            if sms_list:
                code = sms_list[0].get("code") or sms_list[0].get("text")
                st.session_state.sms_code = code
                st.session_state.start_time = None
    except: pass

# =============================
# ARAYÜZ
# =============================

if not st.session_state.order_id:
    # --- NUMARA YOKSA ---
    st.info("Sistem Hazır.")
    if st.button("🚀 YENİ NUMARA AL", type="primary"):
        buy_number()
        st.rerun()

else:
    # --- NUMARA VARSA ---
    
    st.write("🌍 **Tam Numara (+44)**")
    st.code(st.session_state.phone_full, language="text")

    st.write("🏠 **Sadece Numara (KODSUZ)**")
    st.code(st.session_state.phone_local, language="text")

    st.divider()

    st.write("📩 **SMS Kodu**")
    if st.session_state.sms_code:
        st.success("KOD GELDİ!")
        st.code(st.session_state.sms_code, language="text")
    else:
        st.code(".....", language="text")

    st.divider()

    # --- BUTONLAR (GÖRÜNÜR YERDE) ---
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚫 Banla", use_container_width=True):
            ban_order()
            st.rerun()
    with c2:
        if st.button("❌ İptal", type="primary", use_container_width=True):
            cancel_order()
            st.rerun()

    # --- OTOMATİK YENİLEME ---
    if not st.session_state.sms_code:
        elapsed = int(time.time() - st.session_state.start_time)
        rem = MAX_WAIT_SECONDS - elapsed
        
        if rem > 0:
            m, s = divmod(rem, 60)
            st.caption(f"⏳ Bekleniyor... {m}:{s:02d}")
            check_sms()
            if not st.session_state.sms_code:
                time.sleep(3)
                st.rerun()
        else:
            st.error("Süre Doldu.")

    # Alt boşluk
    st.write("\n" * 3)
