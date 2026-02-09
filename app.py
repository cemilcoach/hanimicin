import time
import hashlib
import streamlit as st
import requests
import re
from datetime import datetime

# =============================
# AYARLAR & API ANAHTARLARI
# =============================

# 1. MAIL API (SmailPro) - DİREKT KOD İÇİNDE (Senin verdiğin)
MAIL_API_KEY = "152d9e77387b7f794fc09768291d303a0f0996a3c56d2d45c5fa08f931110361"

# 2. SMS API (5sim) - Hala secrets dosyasından okur
SMS_API_KEY = st.secrets.get("FIVESIM_TOKEN", "TOKEN_YOK")

# ŞİFRE HASH (Secrets'tan okur)
PASSWORD_HASH = st.secrets.get("PANEL_PASSWORD_HASH", "")

# URL'ler
SMS_BASE_URL = "https://5sim.net/v1"
MAIL_BASE_URL = "https://app.sonjj.com/v1"

# SMS Ayarları
SMS_COUNTRY = "england"
SMS_OPERATOR = "virtual58"
SMS_PRODUCT = "uber"

MAX_WAIT_SECONDS = 900 

st.set_page_config(page_title="Comms Panel", layout="centered", initial_sidebar_state="collapsed")

# =============================
# CSS (MOBİL UYUMLU & BUTONLAR YUKARIDA)
# =============================
st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem !important; 
            padding-bottom: 8rem !important; /* Alt kısım rahat olsun */
        }
        
        /* Buton Stilleri */
        .stButton button {
            height: 3.5rem !important;
            width: 100% !important;
            font-size: 16px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
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
# STATE YÖNETİMİ
# =============================
for key in ["mode", "id", "address", "address_secondary", "content", "status", "start_time", "mail_timestamp"]:
    if key not in st.session_state:
        st.session_state[key] = None

# =============================
# API: SMS (5sim)
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
    except Exception as e: st.error(f"Bağlantı: {e}")

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
# API: MAIL (SmailPro)
# =============================
def get_mail(provider="gmail"):
    # API Key direkt yukarıdaki değişkenden geliyor
    headers = {"X-Api-Key": MAIL_API_KEY, "Accept": "application/json"}
    endpoint = "temp_gmail" if provider == "gmail" else "temp_outlook"
    
    try:
        # 1. Listeyi Çek
        r = requests.get(f"{MAIL_BASE_URL}/{endpoint}/list", headers=headers, timeout=10)
        data = r.json()
        
        # Veri yapısını kontrol et (Liste mi, Dict mi?)
        email_list = []
        if isinstance(data, list):
            email_list = data
        elif isinstance(data, dict):
            email_list = data.get("data", [])

        if email_list:
            # İlk maili al
            item = email_list[0]
            selected_email = None
            
            # Gmail bazen 'email', Outlook bazen 'emails' arrayi döner
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
                # Timestamp: Şu andan sonrasını getir
                st.session_state.mail_timestamp = int(time.time())
            else:
                st.error("Mail yapısı çözülemedi.")
        else:
            st.error(f"{provider.capitalize()} havuzu boş veya API key hatası.")
            
    except Exception as e:
        st.error(f"Mail API Hatası: {e}")

def check_mail():
    if not st.session_state.mode or "SMS" in st.session_state.mode: return
    
    headers = {"X-Api-Key": MAIL_API_KEY, "Accept": "application/json"}
    provider = "temp_gmail" if st.session_state.mode == "GMAIL" else "temp_outlook"
    email = st.session_state.address
    ts = st.session_state.mail_timestamp
    
    try:
        url = f"{MAIL_BASE_URL}/{provider}/inbox?email={email}&timestamp={ts}"
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        
        messages = data.get("messages", [])
        if messages:
            msg = messages[0]
            msg_id = msg.get("mid")
            subject = msg.get("textSubject", "Konu Yok")
            
            # İçeriği al
            body_url = f"{MAIL_BASE_URL}/{provider}/message?email={email}&mid={msg_id}"
            r_body = requests.get(body_url, headers=headers, timeout=5)
            body_data = r_body.json()
            body_content = body_data.get("body", "İçerik yok.")
            
            # Kod Bulma (4-8 haneli sayı)
            code_match = re.search(r'\b\d{4,8}\b', body_content)
            found_code = code_match.group(0) if code_match else "Kod Regex Bulamadı"
            
            final_content = f"📌 **{subject}**\n\n🔑 **KOD:** `{found_code}`\n\n📄 **Özet:** {body_content[:150]}..."
            
            st.session_state.content = final_content
            st.session_state.status = "GELDİ"
            st.session_state.start_time = None
    except: pass

def reset_state():
    for key in ["mode", "id", "address", "address_secondary", "content", "status", "start_time", "mail_timestamp"]:
        st.session_state[key] = None

# =============================
# ARAYÜZ (3 BUTON EN ÜSTTE)
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
    if st.button("📧 OUTLOOK\n(Hotmail)", type="primary" if st.session_state.mode == "OUTLOOK" else "secondary"):
        reset_state()
        get_mail("outlook")
        st.rerun()

st.markdown("---")

# =============================
# DETAY EKRANI
# =============================
if st.session_state.address:
    
    # 1. ADRES KUTULARI
    if st.session_state.mode == "SMS":
        st.caption("🟢 AKTİF: SMS")
        st.write("**🌍 Tam Numara (+44)**")
        st.code(st.session_state.address, language="text")
        st.write("**🏠 Sadece Numara**")
        st.code(st.session_state.address_secondary, language="text")
    else:
        st.caption(f"🔵 AKTİF: {st.session_state.mode}")
        st.write(f"**📬 {st.session_state.mode} Adresi**")
        st.code(st.session_state.address, language="text")

    st.divider()

    # 2. GELEN KUTUSU
    st.write("**📩 Gelen Kutusu**")
    
    if st.session_state.content:
        st.success("YENİ MESAJ!")
        if st.session_state.mode == "SMS":
            st.code(st.session_state.content, language="text")
        else:
            st.markdown(st.session_state.content)
    else:
        st.code("..... Bekleniyor .....", language="text")
        
        # OTOMATİK YENİLEME
        if st.session_state.start_time:
            elapsed = int(time.time() - st.session_state.start_time)
            rem = MAX_WAIT_SECONDS - elapsed
            
            if rem > 0:
                m, s = divmod(rem, 60)
                st.caption(f"⏳ Yenileniyor... {m}:{s:02d}")
                
                # API Kontrol
                if st.session_state.mode == "SMS": check_sms()
                else: check_mail()
                
                if not st.session_state.content:
                    time.sleep(4) 
                    st.rerun()
            else:
                st.error("Süre Doldu.")

    st.write("") 
    
    # 3. AKSİYON BUTONLARI
    col_act1, col_act2 = st.columns(2)
    
    with col_act1:
        if st.session_state.mode == "SMS":
            if st.button("🚫 Banla", use_container_width=True):
                ban_sms()
                st.rerun()
        else:
            if st.button("🗑️ Temizle", use_container_width=True):
                reset_state()
                st.rerun()

    with col_act2:
        if st.button("❌ İptal / Durdur", type="primary", use_container_width=True):
            if st.session_state.mode == "SMS": cancel_sms()
            else: reset_state()
            st.rerun()

else:
    st.info("👆 Servis seçerek başlayın.")
    
# Alt boşluk
st.write("\n" * 5)
