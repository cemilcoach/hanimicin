import time
import hashlib
import streamlit as st
import requests
import re
from datetime import datetime

# =============================
# AYARLAR
# =============================

# 1. MAIL API (SmailPro / Sonjj)
MAIL_API_KEY = "152d9e77387b7f794fc09768291d303a0f0996a3c56d2d45c5fa08f931110361"

# 2. SMS API (5sim)
SMS_API_KEY = st.secrets.get("FIVESIM_TOKEN", "TOKEN_YOK")
PASSWORD_HASH = st.secrets.get("PANEL_PASSWORD_HASH", "")

# URL'ler
SMS_BASE_URL = "https://5sim.net/v1"
MAIL_BASE_URL = "https://app.sonjj.com/v1"

# SMS Sabitleri
SMS_COUNTRY = "england"
SMS_OPERATOR = "virtual58"
SMS_PRODUCT = "uber"
MAX_WAIT_SECONDS = 900 

st.set_page_config(page_title="Comms Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS (KESİN UI ÇÖZÜMÜ)
# =============================
st.markdown("""
    <style>
        /* 1. HEADER KAYMASINI ENGELLE */
        .block-container {
            padding-top: 4rem !important; 
            padding-bottom: 15rem !important; /* ALTTA DEVASA BOŞLUK */
        }
        
        /* 2. BUTONLARI SAĞLAMLAŞTIR */
        .stButton button {
            height: 4rem !important;
            width: 100% !important;
            font-size: 18px !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        
        /* 3. KOD KUTULARINI BÜYÜT */
        .stCode { font-size: 1.2rem !important; }
        
        /* 4. MOBİL İÇİN BOŞLUKLARI AYARLA */
        div[data-testid="stVerticalBlock"] {gap: 1rem;}
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
for key in ["mode", "id", "address", "address_secondary", "content", "status", "start_time", "mail_timestamp"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# SMS FONKSİYONLARI
# =============================
def buy_sms():
    headers = {"Authorization": f"Bearer {SMS_API_KEY}", "Accept": "application/json"}
    try:
        url = f"{SMS_BASE_URL}/user/buy/activation/{SMS_COUNTRY}/{SMS_OPERATOR}/{SMS_PRODUCT}"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if "id" in data:
            full = data["phone"]
            local = full[3:] if full.startswith("+44") else (full[2:] if full.startswith("44") else full)
            
            st.session_state.mode = "SMS"
            st.session_state.id = data["id"]
            st.session_state.address = full
            st.session_state.address_secondary = local
            st.session_state.content = None
            st.session_state.status = "BEKLİYOR"
            st.session_state.start_time = time.time()
        else: st.error(f"SMS Hata: {data}")
    except Exception as e: st.error(f"SMS Bağlantı: {e}")

def check_sms():
    if not st.session_state.id: return
    headers = {"Authorization": f"Bearer {SMS_API_KEY}", "Accept": "application/json"}
    try:
        r = requests.get(f"{SMS_BASE_URL}/user/check/{st.session_state.id}", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            st.session_state.status = data.get("status")
            if data.get("sms"):
                code = data["sms"][0].get("code") or data["sms"][0].get("text")
                st.session_state.content = code
                st.session_state.start_time = None
    except: pass

def cancel_sms():
    if st.session_state.id and st.session_state.mode == "SMS":
        headers = {"Authorization": f"Bearer {SMS_API_KEY}", "Accept": "application/json"}
        requests.get(f"{SMS_BASE_URL}/user/cancel/{st.session_state.id}", headers=headers)
        reset_state()

def ban_sms():
    if st.session_state.id and st.session_state.mode == "SMS":
        headers = {"Authorization": f"Bearer {SMS_API_KEY}", "Accept": "application/json"}
        requests.get(f"{SMS_BASE_URL}/user/ban/{st.session_state.id}", headers=headers)
        reset_state()

# =============================
# MAIL FONKSİYONLARI (DEBUG EKLENDİ)
# =============================
def get_mail(provider="gmail"):
    # Debug: Hangi endpoint'e gidiyoruz?
    endpoint = "temp_gmail" if provider == "gmail" else "temp_outlook"
    url = f"{MAIL_BASE_URL}/{endpoint}/list"
    
    headers = {
        "X-Api-Key": MAIL_API_KEY,
        "Accept": "application/json"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        
        # --- HATA AYIKLAMA KISMI ---
        if r.status_code != 200:
            st.error(f"❌ API Hatası! Kodu: {r.status_code}")
            st.code(r.text, language="json") # Hatanın ne olduğunu ekrana basar
            return

        data = r.json()
        
        # Veri yapısını kontrol et
        email_list = []
        if isinstance(data, list):
            email_list = data
        elif isinstance(data, dict):
            email_list = data.get("data", [])
        
        if not email_list:
            st.warning(f"⚠️ {provider.capitalize()} havuzu şu an boş veya yetki yok.")
            st.json(data) # Gelen boş veriyi göster
            return

        # Mail Seçimi
        item = email_list[0]
        selected_email = None
        
        # Esnek parsing (bazen string, bazen dict dönebilir)
        if isinstance(item, dict):
            if "email" in item: selected_email = item["email"]
            elif "emails" in item and len(item["emails"]) > 0: selected_email = item["emails"][0]
        elif isinstance(item, str):
            selected_email = item

        if selected_email:
            st.session_state.mode = "GMAIL" if provider == "gmail" else "OUTLOOK"
            st.session_state.id = provider 
            st.session_state.address = selected_email
            st.session_state.address_secondary = None
            st.session_state.content = None
            st.session_state.status = "MAIL_BEKLİYOR"
            st.session_state.start_time = time.time()
            st.session_state.mail_timestamp = int(time.time())
        else:
            st.error("Mail yapısı anlaşılamadı.")
            st.json(item)

    except Exception as e:
        st.error(f"Bağlantı Hatası: {str(e)}")

def check_mail():
    if not st.session_state.mode or "SMS" in st.session_state.mode: return
    
    headers = {"X-Api-Key": MAIL_API_KEY, "Accept": "application/json"}
    provider = "temp_gmail" if st.session_state.mode == "GMAIL" else "temp_outlook"
    email = st.session_state.address
    ts = st.session_state.mail_timestamp
    
    try:
        # Sadece yeni mesajlar
        url = f"{MAIL_BASE_URL}/{provider}/inbox?email={email}&timestamp={ts}"
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            messages = data.get("messages", [])
            
            if messages:
                msg = messages[0]
                msg_id = msg.get("mid")
                subject = msg.get("textSubject", "Konu Yok")
                
                # İçeriği Çek
                body_url = f"{MAIL_BASE_URL}/{provider}/message?email={email}&mid={msg_id}"
                r_body = requests.get(body_url, headers=headers, timeout=5)
                body_content = "İçerik Alınamadı"
                if r_body.status_code == 200:
                    body_content = r_body.json().get("body", "")
                
                # Kod Ayıkla
                code_match = re.search(r'\b\d{4,8}\b', body_content)
                found_code = code_match.group(0) if code_match else "Kod Yok"
                
                final_content = f"📌 **{subject}**\n\n🔑 **KOD:** `{found_code}`\n\n📄 **Özet:** {body_content[:200]}..."
                
                st.session_state.content = final_content
                st.session_state.status = "GELDİ"
                st.session_state.start_time = None
    except: pass

def reset_state():
    for key in ["mode", "id", "address", "address_secondary", "content", "status", "start_time", "mail_timestamp"]:
        st.session_state[key] = None

# =============================
# ARAYÜZ
# =============================

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("📱 SMS\n(Uber)", type="primary" if st.session_state.mode == "SMS" else "secondary"):
        if st.session_state.mode == "SMS" and st.session_state.id: cancel_sms()
        reset_state()
        buy_sms()
        st.rerun()

with c2:
    if st.button("📧 GMAIL\n(Google)", type="primary" if st.session_state.mode == "GMAIL" else "secondary"):
        reset_state()
        get_mail("gmail")
        st.rerun()

with c3:
    if st.button("📧 HOTMAIL\n(Outlook)", type="primary" if st.session_state.mode == "OUTLOOK" else "secondary"):
        reset_state()
        get_mail("outlook")
        st.rerun()

st.divider()

# =============================
# DETAYLAR & KUTULAR
# =============================
if st.session_state.address:
    
    # 1. ADRES BİLGİSİ
    if st.session_state.mode == "SMS":
        st.write("🌍 **Tam Numara (+44)**")
        st.code(st.session_state.address, language="text")
        st.write("🏠 **Sadece Numara**")
        st.code(st.session_state.address_secondary, language="text")
    else:
        st.write(f"📬 **{st.session_state.mode} Adresi**")
        st.code(st.session_state.address, language="text")

    st.divider()

    # 2. GELEN KUTUSU
    st.write("📩 **Gelen Kod/Mesaj**")
    
    if st.session_state.content:
        st.success("MESAJ GELDİ!")
        if st.session_state.mode == "SMS":
            st.code(st.session_state.content, language="text")
        else:
            st.markdown(st.session_state.content)
    else:
        st.code("..... Bekleniyor .....", language="text")
        
        # Otomatik Yenileme
        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            rem = MAX_WAIT_SECONDS - elapsed
            
            if rem > 0:
                m, s = divmod(rem, 60)
                st.caption(f"⏳ Kontrol ediliyor... {m}:{s:02d}")
                
                if st.session_state.mode == "SMS": check_sms()
                else: check_mail()
                
                if not st.session_state.content:
                    time.sleep(4)
                    st.rerun()
            else:
                st.error("Süre Doldu.")

    st.divider()

    # 3. BUTONLAR
    c1, c2 = st.columns(2)
    with c1:
        if st.session_state.mode == "SMS":
            if st.button("🚫 Banla", use_container_width=True):
                ban_sms()
                st.rerun()
        else:
            if st.button("🗑️ Temizle", use_container_width=True):
                reset_state()
                st.rerun()
                
    with c2:
        if st.button("❌ İptal / Durdur", type="primary", use_container_width=True):
            if st.session_state.mode == "SMS": cancel_sms()
            else: reset_state()
            st.rerun()

else:
    st.info("👆 Servis Seçiniz.")

# =============================
# SAYFA SONU BOŞLUĞU (SCROLL FIX)
# =============================
# Bu kısım sayfanın altına görünmez boşluk ekler, böylece scroll yapınca butonlar yukarı çıkar.
st.write("\n" * 15) 
st.markdown("<br>" * 10, unsafe_allow_html=True)
