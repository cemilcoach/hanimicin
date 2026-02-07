import time
import hashlib
import streamlit as st
import requests
from datetime import datetime

# =============================
# STREAMLIT SECRETS (Cloud)
# =============================
API_KEY = st.secrets["FIVESIM_TOKEN"]
PASSWORD_HASH = st.secrets["PANEL_PASSWORD_HASH"]

BASE_URL = "https://5sim.net/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# SABİT AYARLAR
COUNTRY = "england"
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 180  # 3 dakika

# =============================
# SAYFA AYARLARI
# =============================
st.set_page_config(page_title="Panel Giriş", layout="centered")

# =============================
# LOGIN (ŞİFRE EKRANI)
# =============================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Panel Giriş")

        pwd = st.text_input("Panel Şifresi", type="password")

        if st.button("Giriş Yap"):
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
# UYGULAMA BAŞLIYOR
# =============================
st.title("📱 SMS Panel")

# ====== SESSION STATE ======
for key in ["order_id", "phone", "sms_code", "status", "log"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.log is None:
    st.session_state.log = []

# ====== LOG FONKSİYONU ======
def add_log(action, info=""):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.log.append(f"[{ts}] {action} {info}")

# ====== GÜVENLİ BUY_NUMBER (JSON HATASI DÜZELTİLDİ) ======
def buy_number():
    url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)

        # ---- HTTP STATUS KONTROLÜ ----
        if r.status_code != 200:
            st.error(f"HTTP Hata: {r.status_code}")
            st.text(r.text[:500])
            add_log("HTTP_ERROR", f"{r.status_code}")
            return None, None

        # ---- GÜVENLİ JSON PARSE ----
        try:
            data = r.json()
        except Exception as e:
            st.error("5sim JSON dönmedi!")
            st.text(r.text[:500])
            add_log("JSON_ERROR", str(e))
            return None, None

        if "id" not in data:
            st.error(f"API Hatası: {data}")
            add_log("ERROR", str(data))
            return None, None

        st.session_state.order_id = data["id"]
        st.session_state.phone = data["phone"]
        st.session_state.sms_code = None
        st.session_state.status = "PENDING"

        add_log("BUY", f"Order {data['id']}")
        return data["id"], data["phone"]

    except requests.exceptions.RequestException as e:
        st.error(f"Bağlantı hatası: {e}")
        add_log("REQUEST_ERROR", str(e))
        return None, None

def check_sms(order_id):
    url = f"{BASE_URL}/user/check/{order_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.json()

def cancel_order(order_id):
    url = f"{BASE_URL}/user/cancel/{order_id}"
    res = requests.get(url, headers=HEADERS).json()
    add_log("CANCEL", f"Order {order_id}")
    return res

def ban_order(order_id):
    url = f"{BASE_URL}/user/ban/{order_id}"
    res = requests.get(url, headers=HEADERS).json()
    add_log("BAN", f"Order {order_id}")
    return res

# =============================
# MODERN BUTON SATIRI
# =============================
st.markdown("### 🚀 Kontrol Paneli")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("🟢 Yeni Numara Al"):
        with st.spinner("Numara alınıyor..."):
            time.sleep(2)  # rate-limit güvenliği
            buy_number()

with c2:
    if st.session_state.order_id and st.button("❌ Cancel"):
        cancel_order(st.session_state.order_id)
        buy_number()  # TEK TIKLA YENİ NUMARA

with c3:
    if st.session_state.order_id and st.button("🚫 Ban"):
        ban_order(st.session_state.order_id)
        buy_number()  # TEK TIKLA YENİ NUMARA

st.markdown("---")

# =============================
# NUMARA GÖSTERİMİ
# =============================
if st.session_state.phone:
    phone = st.session_state.phone
    phone_no_country = phone[3:] if phone.startswith("+") else phone

    st.subheader("📞 Numara")
    st.code(phone)

    st.download_button(
        "📋 Numarayı (ülke kodsuz) kopyala",
        phone_no_country,
        file_name="phone.txt"
    )

st.markdown("---")

# =============================
# SAYAÇ + SMS BEKLEME
# =============================
if st.session_state.order_id:
    st.subheader("📩 SMS Bekleniyor...")

    timer_placeholder = st.empty()
    status_placeholder = st.empty()
    success_card = st.empty()

    start_time = time.time()

    while True:
        elapsed = int(time.time() - start_time)
        remaining = max(0, MAX_WAIT_SECONDS - elapsed)

        timer_placeholder.metric("⏳ Kalan Süre (sn)", remaining)

        data = check_sms(st.session_state.order_id)
        status = data.get("status")
        st.session_state.status = status

        status_placeholder.write(f"**Status:** `{status}`")

        sms_list = data.get("sms", [])

        if sms_list:
            sms = sms_list[0]
            code = sms.get("code") or sms.get("text")
            st.session_state.sms_code = code

            success_card.success("✅ **BAŞARILI! SMS ALINDI**")
            add_log("SMS_RECEIVED", code)
            break

        if remaining == 0:
            st.warning("⏰ Zaman Aşımı!")
            add_log("TIMEOUT", f"Order {st.session_state.order_id}")
            buy_number()  # otomatik yeni numara
            break

        time.sleep(3)

# =============================
# KOD GÖSTERİMİ
# =============================
if st.session_state.sms_code:
    st.subheader("🔑 Gelen Kod")
    st.code(st.session_state.sms_code)

    st.download_button(
        "📋 Kodu Kopyala",
        st.session_state.sms_code,
        file_name="code.txt"
    )

st.markdown("---")

# =============================
# GEÇMİŞ LOG
# =============================
st.subheader("📜 Geçmiş İşlemler (Session Log)")

for line in st.session_state.log[-10:]:
    st.text(line)
