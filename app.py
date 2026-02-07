import time
import hashlib
import streamlit as st
import requests

# =============================
# AYARLAR (SABİT)
# =============================
# Streamlit secrets dosyasından veya varsayılan değerlerden okuma
API_KEY = st.secrets.get("FIVESIM_TOKEN", "TOKEN_YOK")
PASSWORD_HASH = st.secrets.get("PANEL_PASSWORD_HASH", "")

BASE_URL = "https://5sim.net/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# Sabit Değerler
COUNTRY = "england"     # İngiltere (+44)
OPERATOR = "virtual58"
PRODUCT = "uber"
MAX_WAIT_SECONDS = 900  # 15 Dakika (900 saniye)

# Sayfa Yapısı: "wide" (geniş) modda açılır, böylece her şey yan yana sığar
st.set_page_config(page_title="SMS Panel", layout="wide", initial_sidebar_state="collapsed")

# =============================
# CSS İLE SIKIŞTIRMA (Scroll Yok)
# =============================
st.markdown("""
    <style>
        /* Sayfa boşluklarını sıfırla */
        .block-container {padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem;}
        /* Bloklar arası boşluğu azalt */
        div[data-testid="stVerticalBlock"] {gap: 0.5rem;}
        /* Butonları büyüt ve kalınlaştır */
        .stButton button {height: 3rem; width: 100%; font-weight: bold; font-size: 16px;}
        /* Code bloklarının üstündeki boşluğu al */
        .stCode {margin-top: -10px;}
    </style>
""", unsafe_allow_html=True)

# =============================
# GİRİŞ EKRANI
# =============================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        c1, c2, c3 = st.columns([1,1,1]) # Ortada küçük bir kutu olsun
        with c2:
            st.warning("🔐 Panel Girişi")
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

# Gerekli değişkenleri tanımla
for key in ["order_id", "phone_full", "phone_local", "sms_code", "status", "start_time"]:
    if key not in st.session_state:
        st.session_state[key] = None

def buy_number():
    try:
        url = f"{BASE_URL}/user/buy/activation/{COUNTRY}/{OPERATOR}/{PRODUCT}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        
        if "id" in data:
            raw = data["phone"] # Örn: +447123456789
            
            # --- NUMARA AYIKLAMA (Ülke Kodu Silme) ---
            p_full = raw
            p_local = raw
            
            # İngiltere (+44) kontrolü
            if raw.startswith("+44"):
                p_local = raw[3:] # +44'ü at
            elif raw.startswith("44"):
                p_local = raw[2:] # 44'ü at
            
            # State'e kaydet
            st.session_state.order_id = data["id"]
            st.session_state.phone_full = p_full   # Tam numara
            st.session_state.phone_local = p_local # Sadece yerel numara
            st.session_state.sms_code = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
        else:
            st.error(f"Hata: {data}")
    except Exception as e:
        st.error(f"Bağlantı hatası: {e}")

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
                # İlk gelen SMS'i al
                code = sms_list[0].get("code") or sms_list[0].get("text")
                st.session_state.sms_code = code
                st.session_state.start_time = None # Süreyi durdur
    except:
        pass

# =============================
# ARAYÜZ TASARIMI (GRID)
# =============================

# 1. SATIR: KONTROL BUTONLARI (Hepsi Yan Yana)
col1, col2, col3 = st.columns(3)

with col1:
    # Ana İşlem Butonu
    if st.button("✅ YENİ NUMARA AL", use_container_width=True):
        if st.session_state.order_id:
            cancel_order() # Varsa eskisini iptal et
        buy_number()
        st.rerun()

with col2:
    if st.button("❌ İPTAL ET", use_container_width=True, disabled=not st.session_state.order_id):
        cancel_order()
        st.rerun()

with col3:
    if st.button("🚫 BANLA (Numara Bozuk)", use_container_width=True, disabled=not st.session_state.order_id):
        ban_order()
        st.rerun()

st.markdown("---") # İnce bir çizgi

# 2. SATIR: BİLGİ EKRANI
if st.session_state.order_id:
    
    # 2a. NUMARA KUTULARI (Yan Yana)
    c_num1, c_num2 = st.columns(2)
    
    with c_num1:
        st.info("🌍 **Tam Numara (+44)**")
        # st.code otomatik kopyalama butonu içerir
        st.code(st.session_state.phone_full, language="text")
        
    with c_num2:
        st.warning("🏠 **Sadece Numara (KODSUZ)**")
        # Burası istediğin ülke kodsuz kopyalama alanı
        st.code(st.session_state.phone_local, language="text")

    st.markdown("---")

    # 2b. SMS KUTUSU VE DURUM
    if st.session_state.sms_code:
        # --- SMS GELDİĞİNDE ---
        st.success("🎉 SMS ONAY KODU GELDİ!")
        
        # SMS KODU İÇİN BÜYÜK KUTU
        st.markdown("### 👇 Kopyalamak için sağ üste bas:")
        st.code(st.session_state.sms_code, language="text")
        
    else:
        # --- SMS BEKLENİRKEN ---
        elapsed = int(time.time() - st.session_state.start_time)
        remaining = MAX_WAIT_SECONDS - elapsed
        
        if remaining > 0:
            mins, secs = divmod(remaining, 60)
            
            # Durum çubuğu
            st.info(f"⏳ **SMS Bekleniyor...** ({mins}:{secs:02d}) | Durum: `{st.session_state.status}`")
            
            # Otomatik Kontrol Mekanizması
            check_sms()
            
            # Eğer hala gelmediyse sayfayı yenile
            if not st.session_state.sms_code:
                time.sleep(3)
                st.rerun()
        else:
            # Süre bittiğinde
            st.error("⏰ **SÜRE DOLDU (15 Dakika).**")
            st.write("Yeni numara almak için yukarıdaki 'YENİ NUMARA AL' butonuna basınız. Otomatik işlem yapılmadı.")

else:
    # Başlangıç Durumu
    st.info("👆 İşlem yapmak için yukarıdaki **'YENİ NUMARA AL'** butonuna basınız.")

