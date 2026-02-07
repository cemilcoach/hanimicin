import time
import hashlib
import streamlit as st
import requests

# =============================
# AYARLAR (SABİT)
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

# DÜZELTME 1: Layout 'centered' yapıldı (Telefona sığması için)
st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS DÜZELTMELERİ (MOBİL İÇİN)
# =============================
st.markdown("""
    <style>
        /* DÜZELTME 2: Üst boşluğu artırdık (padding-top: 4rem) ki menü altında kalmasın */
        .block-container {
            padding-top: 3rem !important; 
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        /* Bileşenler arası boşluk */
        div[data-testid="stVerticalBlock"] {gap: 0.5rem;}
        
        /* Butonları telefonda daha rahat basılabilir yap */
        .stButton button {
            height: 3.5rem; 
            width: 100%; 
            font-weight: bold; 
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# =============================
# GİRİŞ EKRANI
# =============================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown("### 🔐 Panel Giriş") # Basit başlık
        pwd = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            hashed = hashlib.sha256(pwd.encode()).hexdigest()
            if hashed == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Hatalı şifre")
        return False
    return True

if not check_password():
    st.stop()

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
            raw = data["phone"]
            p_full = raw
            if raw.startswith("+44"):
                p_local = raw[3:]
            elif raw.startswith("44"):
                p_local = raw[2:]
            else:
                p_local = raw
            
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = p_full
            st.session_state.phone_local = p_local
            st.session_state.sms_code = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
        else:
            st.error(f"Hata: {data}")
    except Exception as e:
        st.error(f"Bağlantı: {e}")

def cancel_order():
    if st.session_state.order_id:
        requests.get(f"{BASE_URL}/user/cancel/{st.session_state.order_id}", headers=HEADERS)
        reset_state()

def ban_order():
    if st.session_state.order_id:
        requests.get(f"{BASE_URL}/user/ban/{st.session_state.order_id}", headers=HEADERS)
        reset_state()

def reset_state():
    st.session_state.order_id = None
    st.session_state.phone_full = None
    st.session_state.phone_local = None
    st.session_state.sms_code = None
    st.session_state.start_time = None
    st.session_state.status = None

def check_sms():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/check/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            st.session_state.status = data.get("status")
            sms_list = data.get("sms", [])
            if sms_list:
                code = sms_list[0].get("code") or sms_list[0].get("text")
                st.session_state.sms_code = code
                st.session_state.start_time = None
    except:
        pass

# =============================
# ARAYÜZ (MOBİL UYUMLU)
# =============================

# 1. SATIR: BUTONLAR
# Streamlit mobilde 3 kolonu bazen alt alta atabilir.
# Bunu engellemek zordur ama "centered" modunda en iyi böyle görünür.
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("✅ YENİ AL", use_container_width=True):
        if st.session_state.order_id: cancel_order()
        buy_number()
        st.rerun()

with c2:
    if st.button("❌ İPTAL", use_container_width=True, disabled=not st.session_state.order_id):
        cancel_order()
        st.rerun()

with c3:
    if st.button("🚫 BANLA", use_container_width=True, disabled=not st.session_state.order_id):
        ban_order()
        st.rerun()

st.markdown("---")

# 2. SATIR: NUMARA VE DURUM
if st.session_state.order_id:
    
    # Numaralar
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        st.info("**(+44)**")
        st.code(st.session_state.phone_full, language="text")
    with col_n2:
        st.warning("**Kodsuz**")
        st.code(st.session_state.phone_local, language="text")

    st.markdown("---")

    # SMS Kutusu
    if st.session_state.sms_code:
        st.success("SMS GELDİ!")
        st.code(st.session_state.sms_code, language="text")
    else:
        elapsed = int(time.time() - st.session_state.start_time)
        rem = MAX_WAIT_SECONDS - elapsed
        
        if rem > 0:
            m, s = divmod(rem, 60)
            st.info(f"⏳ **{m}:{s:02d}** | {st.session_state.status}")
            check_sms()
            if not st.session_state.sms_code:
                time.sleep(3)
                st.rerun()
        else:
            st.error("SÜRE BİTTİ.")
else:
    st.info("👆 'YENİ AL' butonuna basınız.")
