import time
import hashlib
import streamlit as st
import requests
from datetime import datetime

# =============================
# AYARLAR VE SABİTLER
# =============================
# Eğer secrets dosyan yoksa hata vermemesi için get kullanabilirsin veya try-except
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
MAX_WAIT_SECONDS = 180

st.set_page_config(page_title="Panel Giriş", layout="centered")

# =============================
# LOGIN FONKSİYONU
# =============================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Panel Giriş")
        pwd = st.text_input("Panel Şifresi", type="password")
        if st.button("Giriş Yap"):
            # Buraya kendi hash'ini veya basitlik için direkt şifreyi koyabilirsin test için
            hashed = hashlib.sha256(pwd.encode()).hexdigest()
            if hashed == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Hatalı şifre")
        return False
    return True

if not check_password():
    st.stop()

# =============================
# STATE BAŞLATMA
# =============================
if "order_start_time" not in st.session_state:
    st.session_state.order_start_time = None

for key in ["order_id", "phone", "sms_code", "status", "log"]:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.log is None:
    st.session_state.log = []

def add_log(action, info=""):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.log.append(f"[{ts}] {action} {info}")

# =============================
# API FONKSİYONLARI
# =============================
def buy_number():
    url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "id" in data:
                st.session_state.order_id = data["id"]
                st.session_state.phone = data["phone"]
                st.session_state.sms_code = None
                st.session_state.status = "PENDING"
                st.session_state.order_start_time = time.time() # Süreyi başlat
                add_log("BUY", f"Order {data['id']}")
            else:
                st.error(f"API Hatası: {data}")
        else:
            st.error(f"HTTP {r.status_code}")
    except Exception as e:
        st.error(f"Hata: {e}")

def check_sms_status():
    if not st.session_state.order_id:
        return

    order_id = st.session_state.order_id
    url = f"{BASE_URL}/user/check/{order_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status")
            st.session_state.status = status
            
            sms_list = data.get("sms", [])
            if sms_list:
                sms = sms_list[0]
                code = sms.get("code") or sms.get("text")
                st.session_state.sms_code = code
                add_log("SMS_RECEIVED", code)
                # SMS gelince zamanlayıcıyı durdurmak için start_time'ı sıfırlayabiliriz
                st.session_state.order_start_time = None 
    except:
        pass

def cancel_order():
    if st.session_state.order_id:
        url = f"{BASE_URL}/user/cancel/{st.session_state.order_id}"
        requests.get(url, headers=HEADERS)
        add_log("CANCEL", st.session_state.order_id)
        # State temizle
        st.session_state.order_id = None
        st.session_state.phone = None
        st.session_state.order_start_time = None

def ban_order():
    if st.session_state.order_id:
        url = f"{BASE_URL}/user/ban/{st.session_state.order_id}"
        requests.get(url, headers=HEADERS)
        add_log("BAN", st.session_state.order_id)
        st.session_state.order_id = None
        st.session_state.phone = None
        st.session_state.order_start_time = None

# =============================
# ARAYÜZ
# =============================
st.title("📱 SMS Panel v2")

# Kontrol Butonları
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🟢 Yeni Numara Al"):
        buy_number()
        st.rerun()

with c2:
    if st.session_state.order_id:
        if st.button("❌ İptal Et"):
            cancel_order()
            st.rerun()

with c3:
    if st.session_state.order_id:
        if st.button("🚫 Banla"):
            ban_order()
            st.rerun()

st.markdown("---")

# Numara ve Durum Gösterimi
if st.session_state.order_id:
    st.info(f"Numara: **{st.session_state.phone}**")
    st.caption(f"Durum: {st.session_state.status}")
    
    # SMS KONTROL MEKANİZMASI (Döngüsüz)
    if not st.session_state.sms_code:
        # Süre kontrolü
        elapsed = int(time.time() - st.session_state.order_start_time)
        remaining = MAX_WAIT_SECONDS - elapsed
        
        if remaining > 0:
            st.progress(1 - (remaining / MAX_WAIT_SECONDS), text=f"SMS Bekleniyor... ({remaining} sn)")
            
            # Arka planda kontrol et
            check_sms_status()
            
            # SMS gelmediyse sayfayı 3 saniye sonra yenile
            if not st.session_state.sms_code:
                time.sleep(3) 
                st.rerun()
        else:
            st.error("Zaman aşımı! Numara iptal ediliyor...")
            cancel_order()
            st.rerun()
    else:
        st.success("SMS GELDİ!")
        st.code(st.session_state.sms_code, language="text")

# Log Gösterimi
with st.expander("İşlem Geçmişi"):
    for line in reversed(st.session_state.log[-10:]):
        st.text(line)
