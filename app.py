import time
import hashlib
import streamlit as st
import requests
from datetime import datetime

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
MAX_WAIT_SECONDS = 900  # 15 Dakika

# Layout centered yapıldı, mobilde tam ekran gibi durması için
st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS İLE GÖRÜNÜMÜ BENZETME
# =============================
st.markdown("""
    <style>
        /* Üst boşluğu ayarla */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
        /* Butonları büyüt */
        .stButton button {
            height: 3rem;
            width: 100%;
            border-radius: 10px;
            font-weight: bold;
        }
        /* Bilgi satırlarını sıkılaştır */
        div[data-testid="stVerticalBlock"] {gap: 0.5rem;}
        
        /* Numara ve Kod kutularını özelleştir */
        .stCode {
            font-size: 1.2rem !important;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# =============================
# GİRİŞ (KALICI)
# =============================
def check_login():
    if st.session_state.get("authenticated", False): return True
    if st.query_params.get("auth") == "ok":
        st.session_state.authenticated = True
        return True

    st.markdown("### 🔐 Giriş")
    pwd = st.text_input("Şifre", type="password")
    if st.button("Giriş Yap"):
        if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.query_params["auth"] = "ok"
            st.rerun()
        else:
            st.error("Hatalı şifre")
    return False

if not check_login(): st.stop()

# =============================
# STATE & FONKSİYONLAR
# =============================
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time", "created_at", "price"]:
    if key not in st.session_state:
        st.session_state[key] = None

def buy_number():
    try:
        url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        
        if "id" in data:
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = data["phone"]
            st.session_state.phone_local = data["phone"].replace("+44", "").replace("44", "", 1) if data["phone"].startswith("44") or data["phone"].startswith("+44") else data["phone"]
            st.session_state.price = data.get("price", "---")
            st.session_state.created_at = datetime.now().strftime("%d %B %H:%M")
            st.session_state.sms_code = None
            st.session_state.status = "PENDING"
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
# ARAYÜZ (EKRAN GÖRÜNTÜSÜNE UYGUN)
# =============================

if not st.session_state.order_id:
    # SİPARİŞ YOKSA -> SADECE BÜYÜK BUTON
    st.info("👋 Yeni numara almak için butona bas.")
    if st.button("➕ YENİ NUMARA AL (Uber)", type="primary"):
        buy_number()
        st.rerun()

else:
    # SİPARİŞ VARSA -> DETAY EKRANI (Screenshottaki gibi)
    
    # 1. Başlık ve ID
    st.markdown(f"#### Order Nº {st.session_state.order_id}")
    st.markdown("---")

    # 2. Detay Listesi (Date, Service, Country vs.)
    # Grid yapısı kullanarak düzenli gösteriyoruz
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.markdown("**Date**")
        st.markdown("**Service**")
        st.markdown("**Country**")
        st.markdown("**Operator**")
        st.markdown("**Price**")
    
    with c2:
        st.markdown(f":grey[{st.session_state.created_at}]")
        st.markdown(f"**{PRODUCT.capitalize()}**")
        st.markdown(f"🇬🇧 {COUNTRY.capitalize()}")
        st.markdown(f"{OPERATOR}")
        st.markdown(f"${st.session_state.price}")

    st.markdown("---")

    # 3. NUMARA KUTUSU (Number Box)
    st.markdown("##### Number")
    # Streamlit'te st.code kutusu otomatik kopyalama butonu içerir (sağ üstte).
    # Mobil görünümde daha rahat olsun diye tam numarayı koydum.
    st.code(st.session_state.phone_full, language="text")
    
    # Ekstra: Sadece numara (kodsuz) isteyenler için ufak not
    st.caption(f"Kodsuz: `{st.session_state.phone_local}`")

    # 4. DURUM VE SMS KUTUSU
    st.markdown("##### Code from SMS")
    
    if st.session_state.sms_code:
        # KOD GELDİ
        st.success("✅ Kod Alındı!")
        st.code(st.session_state.sms_code, language="text")
    else:
        # KOD BEKLENİYOR
        # Burası screenshot'taki gibi boş bir kutu görünümü verir
        st.info("Can't receive OTP yet... Waiting for SMS.")
        # Boş bir code bloğu koyuyoruz ki yeri belli olsun
        st.code("   Wait...   ", language="text") 
        
        # 5. TIMER (Progress Bar)
        elapsed = int(time.time() - st.session_state.start_time)
        rem = MAX_WAIT_SECONDS - elapsed
        if rem > 0:
            m, s = divmod(rem, 60)
            prog = max(0.0, min(1.0, 1 - (elapsed / MAX_WAIT_SECONDS)))
            st.progress(prog)
            st.caption(f"{m} minutes left ({st.session_state.status})")
            
            # Otomatik Kontrol
            check_sms()
            time.sleep(3)
            st.rerun()
        else:
            st.error("Süre Doldu.")

    st.markdown("---")

    # 6. ALT BUTONLAR (Ban ve Cancel)
    # Screenshot'taki gibi yan yana
    col_ban, col_cancel = st.columns(2)

    with col_ban:
        # Ban butonu (Genelde beyaz/outline olur ama streamlit'te secondary gri yapar)
        if st.button("🚫 Ban", use_container_width=True):
            ban_order()
            st.rerun()

    with col_cancel:
        # Cancel butonu (Mavi/Primary)
        if st.button("❌ Cancel", type="primary", use_container_width=True):
            cancel_order()
            st.rerun()
