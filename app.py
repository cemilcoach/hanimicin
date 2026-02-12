import time
import hashlib
import streamlit as st
import requests
import re
import base64
import streamlit.components.v1 as components

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

# SADECE İNGİLTERE AYARLARI
COUNTRY = "england"
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900 

# SES (BASE64)
BEEP_SOUND = """
data:audio/mp3;base64,SUQzBAAAAAABAFRYWFgAAAASAAADbWFqb3JfYnJhbmQAbXA0MgBUWFhYAAAAEQAAA21pbm9yX3ZlcnNpb24AMABUWFhYAAAAHAAAA2NvbXBhdGlibZVfYnJhbmRzAGlzb21tcDQyAFRTU0UAAAAPAAADTGF2ZjU3LjU2LjEwMAAAAAAAAAAAAAAA//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq
"""

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS
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
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time", "raw_data", "error_msg"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# JS LINK ACMA
# =============================
def open_multi_tabs():
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
            background-color: #2e7bcf;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            font-family: sans-serif;
            margin-bottom: 5px;
        }
    </style>
    <button class="multi-btn" onclick="openSites()">🌐 Uber & Mail Aç</button>
    """
    components.html(html_code, height=60)

# =============================
# FONKSİYONLAR
# =============================
def buy_number():
    msg_box = st.empty()
    msg_box.info("🇬🇧 İngiltere alınıyor...", icon="🚀")
    
    try:
        url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        
        if "id" in data:
            full = data["phone"]
            local = full.replace("+", "")
            if local.startswith("44"): local = local[2:]
            
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = full
            st.session_state.phone_local = local
            st.session_state.sms_code = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
            st.session_state.raw_data = None
            st.session_state.error_msg = None
            return
        else:
            st.session_state.error_msg = f"❌ STOK YOK! Hata: {data}"
            
    except Exception as e:
        st.session_state.error_msg = f"Bağlantı Hatası: {e}"

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
                full_text = sms_list[0].get("text")
                if not full_text: full_text = sms_list[0].get("code")
                if not full_text: full_text = str(sms_list[0])
                
                st.session_state.sms_code = full_text
                st.session_state.start_time = None 
                return True
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
        st.error(f"Bağlantı: {e}")

def ban_order():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/ban/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            st.toast("✅ Banlandı!", icon="🚫")
            reset_state()
        else:
            st.error(f"Banlanamadı: {r.json()}")
    except Exception as e:
        st.error(f"Bağlantı: {e}")

def finish_order():
    """Siparişi başarılı olarak tamamlar"""
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/finish/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            st.toast("✅ Tamamlandı!", icon="✨")
            reset_state()
        else:
            # Bazen süre bitince finish hata verebilir ama biz yine de ekranı temizleyelim
            st.toast("Tamamlandı (Sunucu yanıt vermese de)", icon="👍")
            reset_state()
    except:
        reset_state()

def reset_state():
    for key in ["order_id", "phone_full", "phone_local", "sms_code", "start_time", "status", "raw_data", "error_msg"]:
        st.session_state[key] = None

# =============================
# ARAYÜZ
# =============================

open_multi_tabs()

if not st.session_state.order_id:
    # --- NUMARA ALMA ---
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
        if st.button("🗑️ Temizle"):
            st.session_state.error_msg = None
            st.rerun()

    if st.button("🚀 NUMARA AL (🇬🇧 İngiltere)", type="primary"):
        buy_number()
        st.rerun()

else:
    # --- NUMARA VARSA ---
    st.write("🌍 **Tam Numara (İngiltere)**")
    st.code(st.session_state.phone_full, language="text")

    st.write("🏠 **Sadece Numara (KODSUZ)**")
    st.code(st.session_state.phone_local, language="text")

    # SMS Kutusu
    st.write("📩 **SMS Kodu**")
    
    if st.session_state.sms_code:
        # --- SMS GELDİ ---
        st.success("MESAJ GELDİ!")
        st.code(st.session_state.sms_code, language="text")
        
        # SES
        st.markdown(f"""
            <audio autoplay="true">
            <source src="{BEEP_SOUND}" type="audio/mp3">
            </audio>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        # --- SMS GELİNCE SADECE TAMAMLA TUŞU ---
        if st.button("✅ Tamamla", type="primary", use_container_width=True):
            finish_order()
            st.rerun()

    else:
        # --- SMS BEKLENİYOR ---
        st.code(".....", language="text")
        
        st.divider()

        # --- SMS GELMEDEN ÖNCE BAN/İPTAL TUŞLARI ---
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🚫 Banla", use_container_width=True):
                ban_order()
                st.rerun()
        with c2:
            if st.button("❌ İptal", type="primary", use_container_width=True):
                cancel_order()
                st.rerun()

    # OTOMATİK KONTROL (Sadece SMS gelmediyse çalışır)
    if not st.session_state.sms_code:
        if st.button("🔄 Manuel Kontrol"):
            if check_sms(): st.rerun()
            else: st.toast("Henüz SMS Yok")

        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            rem = MAX_WAIT_SECONDS - elapsed
            
            if rem > 0:
                m, s = divmod(rem, 60)
                st.caption(f"⏳ Bekleniyor... {m}:{s:02d}")
                
                found = check_sms()
                if found:
                    st.rerun()
                else:
                    time.sleep(3)
                    st.rerun()
            else:
                st.error("Süre Doldu.")

    st.write("\n" * 10)
