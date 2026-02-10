import time
import hashlib
import streamlit as st
import requests
import re

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
# CSS
# =============================
st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem !important; 
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
        /* Kod kutusunu büyüt ve kaydırılabilir yap */
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
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/check/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            st.session_state.raw_data = data 
            st.session_state.status = data.get("status")
            
            sms_list = data.get("sms", [])
            if sms_list:
                # --- GÜNCELLENEN MANTIK: HER ŞEYİ AL ---
                # Öncelik: Mesajın tamamı (text)
                full_text = sms_list[0].get("text")
                
                # Eğer text boşsa, 'code' alanını dene
                if not full_text:
                    full_text = sms_list[0].get("code")
                
                # Eğer hala boşsa, ham veriyi string olarak bas (ki boş kalmasın)
                if not full_text:
                    full_text = str(sms_list[0])
                
                # State'e kaydet
                st.session_state.sms_code = full_text
                st.session_state.start_time = None 
                
                # ÖNEMLİ: Kod bulunduysa True dön ki arayüz yenilensin
                return True
    except: pass
    return False

# --- İPTAL FONKSİYONLARI ---
def cancel_order():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/cancel/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if r.status_code == 200:
            st.toast("✅ İptal Başarılı!", icon="🗑️")
            reset_state()
        else:
            st.error(f"❌ İptal Edilemedi! 5sim: {data}")
    except Exception as e:
        st.error(f"Bağlantı: {e}")

def ban_order():
    if not st.session_state.order_id: return
    try:
        url = f"{BASE_URL}/user/ban/{st.session_state.order_id}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        if r.status_code == 200:
            st.toast("✅ Banlandı!", icon="🚫")
            reset_state()
        else:
            st.error(f"❌ Banlanamadı! 5sim: {data}")
    except Exception as e:
        st.error(f"Bağlantı: {e}")

def reset_state():
    for key in ["order_id", "phone_full", "phone_local", "sms_code", "start_time", "status", "raw_data", "current_country", "error_msg"]:
        st.session_state[key] = None

# =============================
# ARAYÜZ
# =============================

if not st.session_state.order_id:
    # --- HAZIR ---
    st.info("Sistem Hazır. (6sn Portekiz -> İngiltere)")
    
    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
        if st.button("🗑️ Temizle"):
            st.session_state.error_msg = None
            st.rerun()

    if st.button("🚀 NUMARA AL (Uber)", type="primary"):
        buy_number()
        st.rerun()

else:
    # --- NUMARA VARSA ---
    
    st.markdown(f"### {st.session_state.current_country}")
    
    st.write("🌍 **Tam Numara**")
    st.code(st.session_state.phone_full, language="text")

    st.write("🏠 **Sadece Numara (KODSUZ)**")
    st.code(st.session_state.phone_local, language="text")

    # --- SMS KUTUSU ---
    st.write("📩 **SMS Kodu**")
    
    if st.session_state.sms_code:
        st.success("MESAJ GELDİ!")
        # BURADA MESAJIN TAMAMI YAZACAK
        st.code(st.session_state.sms_code, language="text")
        
        # SES
        st.markdown("""
            <audio autoplay="true">
            <source src="https://upload.wikimedia.org/wikipedia/commons/a/a5/Glass_ping-sound.wav" type="audio/wav">
            </audio>
            """, unsafe_allow_html=True)
    else:
        st.code(".....", language="text")

    st.divider()

    # BUTONLAR
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚫 Banla", use_container_width=True):
            ban_order()
            st.rerun()
    with c2:
        if st.button("❌ İptal", type="primary", use_container_width=True):
            cancel_order()
            st.rerun()

    # OTOMATİK KONTROL
    if not st.session_state.sms_code:
        if st.button("🔄 Manuel Kontrol"):
            if check_sms():
                st.rerun() # Bulursa yenile
            else:
                st.toast("Henüz SMS Yok")

        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            rem = MAX_WAIT_SECONDS - elapsed
            
            if rem > 0:
                m, s = divmod(rem, 60)
                st.caption(f"⏳ Bekleniyor... {m}:{s:02d}")
                
                # Arka planda kontrol et
                found = check_sms()
                
                if found:
                    st.rerun() # <--- KRİTİK NOKTA: KOD BULUNDUYSA HEMEN YENİLE!
                else:
                    time.sleep(3)
                    st.rerun()
            else:
                st.error("Süre Doldu.")

    with st.expander("🛠 Ham Veri"):
        st.json(st.session_state.raw_data)

    st.write("\n" * 10)
