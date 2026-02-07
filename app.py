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

# SABİTLER
COUNTRY = "england"   # İngiltere (+44)
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900  # 15 Dakika

st.set_page_config(page_title="SMS Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# LOGIN VE CSS (Kompakt Görünüm İçin)
# =============================
# Sayfa boşluklarını azaltmak için CSS
st.markdown("""
    <style>
        .block-container {padding-top: 1rem; padding-bottom: 0rem;}
        h1 {margin-top: 0rem; padding-top: 0rem; font-size: 1.5rem;}
        div[data-testid="stVerticalBlock"] > div {padding-bottom: 0.5rem;}
    </style>
""", unsafe_allow_html=True)

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Giriş")
        pwd = st.text_input("Şifre", type="password")
        if st.button("Giriş"):
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
# STATE YÖNETİMİ
# =============================
if "order_start_time" not in st.session_state:
    st.session_state.order_start_time = None

# Gerekli değişkenleri tanımla
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "log"]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.log is None:
    st.session_state.log = []

def add_log(action, info=""):
    ts = datetime.now().strftime("%H:%M")
    st.session_state.log.insert(0, f"[{ts}] {action} {info}") # En yeniyi en üste ekle

# =============================
# API İŞLEMLERİ
# =============================
def buy_number():
    url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "id" in data:
                # Gelen numara: +447123456789
                raw_phone = data["phone"]
                
                # Parse işlemleri (İngiltere +44 varsayımıyla)
                phone_full = raw_phone # +44...
                phone_local = raw_phone.replace("+44", "").replace("44", "", 1) if raw_phone.startswith("44") or raw_phone.startswith("+44") else raw_phone

                st.session_state.order_id = data["id"]
                st.session_state.phone_full = phone_full
                st.session_state.phone_local = phone_local
                st.session_state.sms_code = None
                st.session_state.status = "BEKLİYOR"
                st.session_state.order_start_time = time.time()
                add_log("ALINDI", data['id'])
            else:
                st.error(f"API Hatası: {data}")
        else:
            st.error(f"HTTP {r.status_code}")
    except Exception as e:
        st.error(f"Hata: {e}")

def check_sms_status():
    if not st.session_state.order_id: return

    url = f"{BASE_URL}/user/check/{st.session_state.order_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            st.session_state.status = data.get("status")
            
            sms_list = data.get("sms", [])
            if sms_list:
                sms = sms_list[0]
                code = sms.get("code") or sms.get("text")
                st.session_state.sms_code = code
                st.session_state.order_start_time = None # Sayacı durdur
                add_log("SMS GELDİ", code)
    except:
        pass

def cancel_order():
    if st.session_state.order_id:
        url = f"{BASE_URL}/user/cancel/{st.session_state.order_id}"
        requests.get(url, headers=HEADERS)
        add_log("İPTAL", st.session_state.order_id)
        reset_state()

def ban_order():
    if st.session_state.order_id:
        url = f"{BASE_URL}/user/ban/{st.session_state.order_id}"
        requests.get(url, headers=HEADERS)
        add_log("BAN", st.session_state.order_id)
        reset_state()

def reset_state():
    st.session_state.order_id = None
    st.session_state.phone_full = None
    st.session_state.phone_local = None
    st.session_state.sms_code = None
    st.session_state.order_start_time = None
    st.session_state.status = None

# =============================
# ARAYÜZ (KOMPAKT)
# =============================

# 1. SATIR: BUTONLAR
col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    # Eğer numara yoksa "Yeni Al", varsa buton pasif veya işlevsiz görünsün istersen disable edebilirsin.
    # Ama istek üzerine manuel kontrol tam sende.
    if st.button("🟢 YENİ NUMARA AL", use_container_width=True):
        if st.session_state.order_id: 
            cancel_order() # Öncekini iptal et
        buy_number()
        st.rerun()

with col_btn2:
    if st.button("❌ İPTAL ET", use_container_width=True, disabled=not st.session_state.order_id):
        cancel_order()
        st.rerun()

with col_btn3:
    if st.button("🚫 BANLA", use_container_width=True, disabled=not st.session_state.order_id):
        ban_order()
        st.rerun()

st.divider()

# 2. SATIR: NUMARA BİLGİSİ (Varsa Göster)
if st.session_state.order_id:
    
    # Numara Kopyalama Kutuları (Yan Yana)
    c_num1, c_num2 = st.columns(2)
    
    with c_num1:
        st.caption("🌍 Ülke Kodlu (+44...)")
        st.code(st.session_state.phone_full, language="text")
        
    with c_num2:
        st.caption("🏠 Ülke Kodsuz (7...)")
        st.code(st.session_state.phone_local, language="text")

    # 3. SATIR: SMS DURUMU VE KODU
    
    if st.session_state.sms_code:
        # --- SMS GELDİĞİNDE GÖRÜNECEK ALAN ---
        st.success("✅ SMS ONAY KODU GELDİ!")
        st.markdown("### 👇 KOD AŞAĞIDA")
        st.code(st.session_state.sms_code, language="text") # Kopyalanabilir büyük kutu
        
    else:
        # --- SMS BEKLENİRKEN GÖRÜNECEK ALAN ---
        elapsed = int(time.time() - st.session_state.order_start_time)
        remaining = MAX_WAIT_SECONDS - elapsed
        
        if remaining > 0:
            mins, secs = divmod(remaining, 60)
            st.info(f"⏳ SMS Bekleniyor... Kalan: {mins}:{secs:02d}")
            st.caption(f"Durum: {st.session_state.status}")
            
            # Otomatik Kontrol Döngüsü
            check_sms_status()
            
            if not st.session_state.sms_code:
                time.sleep(3) # 3 saniye bekle
                st.rerun()    # Sayfayı yenile
        else:
            st.error("⏰ SÜRE DOLDU! (Yeni numara için tuşa basmalısın)")
            st.session_state.status = "TIMEOUT"

else:
    st.info("👆 İşlem yapmak için 'Yeni Numara Al' butonuna basın.")

# 4. SATIR: LOG (Gizli/Expander içinde yer kaplamasın)
with st.expander("📜 İşlem Geçmişi (Log)"):
    for line in st.session_state.log[:10]:
        st.text(line)
