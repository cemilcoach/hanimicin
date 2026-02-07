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

# Sabitler
COUNTRY = "england"
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900  # 15 Dakika

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS DÜZELTMELERİ
# =============================
st.markdown("""
    <style>
        /* Alt kısımda butonların kaybolmaması için büyük boşluk */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 8rem !important; /* Alt boşluk artırıldı */
        }
        
        /* Butonları daha büyük ve belirgin yap */
        .stButton button {
            height: 3.5rem;
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
        }

        /* Kod kutularını özelleştir (Daha okunaklı) */
        .stCode {
            font-size: 1.5rem !important; /* Yazı boyutu büyütüldü */
        }
        
        /* Gereksiz boşlukları sil */
        div[data-testid="stVerticalBlock"] {gap: 0.8rem;}
    </style>
""", unsafe_allow_html=True)

# =============================
# GİRİŞ İŞLEMLERİ
# =============================
def check_login():
    if st.session_state.get("authenticated", False): return True
    if st.query_params.get("auth") == "ok":
        st.session_state.authenticated = True
        return True

    st.warning("🔐 Giriş Yap")
    pwd = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.authenticated = True
            st.query_params["auth"] = "ok"
            st.rerun()
        else:
            st.error("Hatalı şifre")
    return False

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
            # Kodsuz numarayı ayıkla (+44 veya 44 sil)
            if full.startswith("+44"): local = full[3:]
            elif full.startswith("44"): local = full[2:]
            else: local = full

            st.session_state.order_id = data["id"]
            st.session_state.phone_full = full
            st.session_state.phone_local = local
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
# ARAYÜZ (SADE & BUTONLAR YUKARIDA)
# =============================

if not st.session_state.order_id:
    # --- SİPARİŞ YOKSA ---
    st.info("Hazır.")
    if st.button("➕ YENİ NUMARA AL", type="primary"):
        buy_number()
        st.rerun()

else:
    # --- SİPARİŞ VARSA ---
    
    # 1. TAM NUMARA
    st.markdown("##### 🌍 Tam Numara (+44)")
    st.code(st.session_state.phone_full, language="text")

    # 2. KODSUZ NUMARA (İsteğin üzerine eklenen özel alan)
    st.markdown("##### 🏠 Sadece Numara (KODSUZ)")
    st.code(st.session_state.phone_local, language="text")

    st.markdown("---")

    # 3. SMS ALANI
    st.markdown("##### 📩 Gelen SMS Kodu")
    
    if st.session_state.sms_code:
        # Kod Geldi
        st.success("KOD GELDİ!")
        st.code(st.session_state.sms_code, language="text")
    else:
        # Bekleniyor
        st.info("SMS Bekleniyor... (Otomatik yenilenir)")
        # Boş kutu (Görüntü bozulmasın diye)
        st.code(".....", language="text")
        
        # Süre Sayacı
        elapsed = int(time.time() - st.session_state.start_time)
        rem = MAX_WAIT_SECONDS - elapsed
        if rem > 0:
            m, s = divmod(rem, 60)
            st.caption(f"Kalan Süre: {m}:{s:02d}")
            check_sms()
            if not st.session_state.sms_code:
                time.sleep(3)
                st.rerun()
        else:
            st.error("Süre Doldu.")

    st.markdown("---")
    st.write("") # Biraz boşluk

    # 4. BUTONLAR (En altta)
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚫 Banla", use_container_width=True):
            ban_order()
            st.rerun()
            
    with col2:
        if st.button("❌ İptal Et", type="primary", use_container_width=True):
            cancel_order()
            st.rerun()

    # Footer altında kalmasın diye ekstra görünmez boşluk
    st.write("\n" * 5)
