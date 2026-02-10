import time
import hashlib
import streamlit as st
import requests
import re
import streamlit.components.v1 as components  # Linkleri açmak için gerekli

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

# --- 1. TERCİH (PORTEKİZ) ---
CFG_1_COUNTRY = "portugal"
CFG_1_OPERATOR = "virtual51"

# --- 2. TERCİH (İNGİLTERE) ---
CFG_2_COUNTRY = "england"
CFG_2_OPERATOR = "virtual58"

PRODUCT = "uber"
MAX_WAIT_SECONDS = 900 

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS (DÜZGÜN GÖRÜNÜM)
# =============================
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem !important; 
            padding-bottom: 10rem !important;
        }
        .stButton button {
            height: 3.5rem !important;
            width: 100% !important;
            font-size: 16px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        /* Kod kutusunu büyüt */
        .stCode { font-size: 1.2rem !important; }
        
        div[data-testid="stVerticalBlock"] {gap: 0.8rem;}
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
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time", "raw_data", "current_country", "error_msg"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# ÇOKLU LİNK AÇMA BUTONU (JAVASCRIPT)
# =============================
def open_multi_tabs():
    # Bu HTML/JS bloğu, butona basıldığında iki siteyi de yeni sekmede açar.
    # Tarayıcı pop-up izni isteyebilir.
    html_code = """
    <script>
    function openSites() {
        window.open('https://m.uber.com', '_blank');
        window.open('https://smailpro.com/temporary-email', '_blank');
    }
    </script>
    <style>
        .multi-btn {
            width: 100%;
            padding: 12px;
            background-color: #2e7bcf; /* Mavi renk */
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            font-family: sans-serif;
            transition: 0.3s;
        }
        .multi-btn:hover {
            background-color: #1a5b9e;
        }
    </style>
    <button class="multi-btn" onclick="openSites()">🌐 Uber & Mail Aç</button>
    """
    # Streamlit içine güvenli HTML gömüyoruz
    components.html(html_code, height=60)

# =============================
# FONKSİYONLAR
# =============================
def buy_number():
    msg_box = st.empty()
    
    # --- ADIM 1: PORTEKİZ (6 Saniye Zorla) ---
    end_time = time.time() + 6
    attempt = 1
    
    while time.time() < end_time:
        msg_box.info(f"🇵🇹 Portekiz deneniyor... ({attempt})", icon="⏳")
        try:
            url1 = f"{BASE_URL}/user/buy/activation/{CFG_1_COUNTRY}/{CFG_1_OPERATOR}/{PRODUCT}"
            r1 = requests.get(url1, headers=HEADERS, timeout=5)
            data1 = r1.json()
            if "id" in data1:
                set_session(data1, "🇵🇹 Portekiz")
                return 
        except: pass 
        attempt += 1
        time.sleep(1.5)

    # --- ADIM 2: İNGİLTERE ---
    msg_box.warning("⚠️ İngiltere'ye geçiliyor...", icon="🔄")
    time.sleep(1)

    msg_box.info("🇬🇧 İngiltere alınıyor...", icon="🚀")
    try:
        url2 = f"{BASE_URL}/user/buy/activation/{CFG_2_COUNTRY}/{CFG_2_OPERATOR}/{PRODUCT}"
        r2 = requests.get(url2, headers=HEADERS, timeout=10)
        data2 = r2.json()
        if "id" in data2:
            set_session(data2, "🇬🇧 İngiltere")
            return
        else:
            st.session_state.error_msg = f"❌ İNGİLTERE DE DOLU! Hata: {data2}"
    except Exception as e:
        st.session_state.error_msg = f"Bağlantı Hatası: {e}"

def set_session(data, country_name):
    full = data["phone"]
    local = full.replace("+", "")
    if local.startswith("44"): local = local[2:]
    elif local.startswith("351"): local = local[3:]
    
    st.session_state.order_id = data["id"]
    st.session_state.phone_full = full
    st.session_state.phone_local = local
    st.session_state.sms_code = None
    st.session_state.status = "BEKLİYOR"
    st.session_state.current_country = country_name
    st.session_state.start_time = time.time()
    st.session_state.raw_data = None
    st.session_state.error_msg = None

def check_sms():
    if not st.session_state.order_id: return False
    try:
        url = f"{BASE_URL}/user/check/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            st.session_state.raw_data = data 
            st.session_state.status = data.get("status")
            
            sms_list = data.get("sms", [])
            if sms_list:
                # --- HER ŞEYİ YAKALA MANTIĞI ---
                full_text = sms_list[0].get("text")
                if not full_text: full_text = sms_list[0].get("code")
                if not full_text: full_text = str(sms_list[0])
                
                st.session_state.sms_code = full_text
                st.session_state.start_time = None 
                return True # Bulundu
    except: pass
    return False

def cancel_order():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/cancel/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            st.toast("✅ İptal Başarılı!", icon="🗑️")
            reset_state()
        else:
            st.error(f"İptal Edilemedi: {r.json()}")
    except Exception as e:
        st.error(f"Bağlantı: {
