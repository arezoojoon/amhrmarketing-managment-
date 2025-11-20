import os
import sqlite3
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# تنظیمات CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
DB_NAME = "amhr_leads.db"

# لینک‌های ضروری
BOOKING_URL = "https://calendly.com/your-link" # لینک کلندلی خود را اینجا قرار دهید
MAP_LINK = "https://maps.google.com/?cid=8846483346399154677&g_mp=Cidnb29nbGUubWFwcy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQ"
LINKEDIN_URL = "https://www.linkedin.com/in/arezoomohammadzadegan/"
CATALOG_URL = "https://amhrd.com/catalog.pdf" # لینک کاتالوگ خدمات شرکت
ARTIN_REPORT_URL = "https://artinsmartagent.com/report.pdf" # لینک گزارش آرتین

# اطلاعات شرکت
COMPANY_NAME = "AMHR MARKETING MANAGEMENT LLC"
CEO_NAME = "Arezoo Mohammadzadegan"
CEO_TITLE = {
    "en": "CEO & Online Business Consultant",
    "fa": "مدیر عامل و مشاور کسب‌وکار آنلاین",
    "ar": "الرئيس التنفيذي ومستشار الأعمال عبر الإنترنت",
    "ru": "Генеральный директор и бизнес-консультант"
}
ADDRESS = "Latifa Towers, Dubai"
WEBSITES = [
    "www.artinwebs.org",
    "www.amhrd.com",
    "artinsmartagent.com"
]

# --- DATABASE ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            chat_id TEXT PRIMARY KEY,
            lang TEXT,
            name TEXT,
            phone TEXT,
            registration_date INTEGER,
            step TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_lead_state(chat_id, lang, name, phone, step):
    conn = get_db_connection()
    timestamp = int(time.time())
    cursor = conn.execute("SELECT * FROM leads WHERE chat_id = ?", (str(chat_id),))
    if cursor.fetchone():
        conn.execute("""
            UPDATE leads 
            SET lang=COALESCE(?, lang), name=COALESCE(?, name), phone=COALESCE(?, phone), step=? 
            WHERE chat_id=?
        """, (lang or None, name or None, phone or None, step, str(chat_id)))
    else:
        conn.execute("INSERT INTO leads (chat_id, lang, name, phone, registration_date, step) VALUES (?, ?, ?, ?, ?, ?)", 
                     (str(chat_id), lang, name, phone, timestamp, step))
    conn.commit()
    conn.close()

def load_lead_state(chat_id):
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM leads WHERE chat_id = ?", (str(chat_id),))
    row = cursor.fetchone()
    conn.close()
    if row: return dict(row)
    return {'step': 'awaiting_lang_selection', 'lang': None}

init_db()

# --- MENU OPTIONS ---
def get_main_menu_options(lang):
    if lang == 'fa': 
        return ["خدمات ما (طراحی وب، سئو، AI)", "پلتفرم هوشمند آرتین", "درباره مدیرعامل و تماس", "رزرو مشاوره", "دریافت کاتالوگ"]
    if lang == 'ar': 
        return ["خدماتنا (ويب، سيو، ذكاء اصطناعي)", "منصة آرتين الذكية", "المدير التنفيذي والاتصال", "حجز استشارة", "تحميل الكتالوج"]
    if lang == 'ru': 
        return ["Услуги (Web, SEO, AI)", "Платформа Artin Smart", "О CEO и Контакты", "Забронировать встречу", "Скачать каталог"]
    # Default English
    return ["Our Services (Web, SEO, AI)", "Artin SmartAgent Platform", "About CEO & Contact", "Book Consultation", "Get Catalog"]

# --- LOGIC ---
async def process_user_input(chat_id: str, text: str, responder_func):
    state = load_lead_state(chat_id)
    step = state.get('step')
    lang = state.get('lang')

    # 0. ریست کردن / شروع
    if text in ["/start", "start", "شروع", "Start"]:
        save_lead_state(chat_id, '', '', '', 'awaiting_lang_selection')
        welcome_msg = (
            f"Welcome to <b>{COMPANY_NAME}</b> 🌐\n"
            "Your 24/7 Digital Marketing & AI Partner.\n\n"
            "Please choose a language / لطفاً زبان خود را انتخاب کنید:"
        )
        await responder_func(welcome_msg, options=["English (EN)", "فارسی (FA)", "العربية (AR)", "Русский (RU)"])
        return

    # 1. انتخاب زبان
    if step == 'awaiting_lang_selection':
        sel_lang = None
        if "EN" in text.upper(): sel_lang = "en"
        elif "FA" in text.upper() or "فارسی" in text: sel_lang = "fa"
        elif "AR" in text.upper() or "العربية" in text: sel_lang = "ar"
        elif "RU" in text.upper() or "РУССКИЙ" in text: sel_lang = "ru"

        if sel_lang:
            save_lead_state(chat_id, sel_lang, '', '', 'awaiting_name')
            prompt = {
                "en": "Thank you. Please enter your Full Name:",
                "fa": "ممنون. لطفاً نام و نام خانوادگی خود را وارد کنید:",
                "ar": "شكراً. الرجاء إدخال اسمك الكامل:",
                "ru": "Спасибо. Пожалуйста, введите ваше полное имя:"
            }[sel_lang]
            await responder_func(prompt)
        else:
            await responder_func("Please select a language:", options=["English (EN)", "فارسی (FA)"])
        return

    # 2. دریافت نام
    if step == 'awaiting_name':
        save_lead_state(chat_id, lang, text, '', 'awaiting_phone')
        prompt = {
            "en": f"Nice to meet you, {text}. To assist you better, please share your WhatsApp number:",
            "fa": f"خوشبختم {text}. برای راهنمایی بهتر، لطفاً شماره واتساپ خود را ارسال کنید:",
            "ar": f"تشرفنا {text}. لخدمتك بشكل أفضل، يرجى مشاركة رقم الواتساب:",
            "ru": f"Приятно познакомиться, {text}. Пожалуйста, укажите ваш номер WhatsApp:"
        }.get(lang, "Send phone:")
        await responder_func(prompt)
        return

    # 3. دریافت شماره و نمایش منو
    if step == 'awaiting_phone':
        save_lead_state(chat_id, lang, state.get('name'), text, 'main_menu')
        welcome = {
            "en": "Registration Complete! How can we help you expand your business?",
            "fa": "ثبت نام تکمیل شد! چگونه می‌توانیم به رشد کسب‌وکار شما کمک کنیم؟",
            "ar": "اكتمل التسجيل! كيف يمكننا مساعدتك في توسيع نطاق عملك؟",
            "ru": "Регистрация завершена! Как мы можем помочь вашему бизнесу?"
        }.get(lang, "Done.")
        await responder_func(welcome, options=get_main_menu_options(lang))
        return

    # 4. منوی اصلی
    if step == 'main_menu':
        
        # --- OPTION 1: SERVICES ---
        if any(x in text for x in ["Services", "خدمات", "Услуги"]):
            msg_en = (
                "🚀 <b>AMHR Digital Services:</b>\n\n"
                "✅ <b>Web Design & SEO:</b> High-performance websites tailored for global reach.\n"
                "✅ <b>Digital Marketing:</b> Strategic campaigns to boost your ROI.\n"
                "✅ <b>Custom AI Agents:</b> Designing dedicated AI agents for your business automation."
            )
            msg_fa = (
                "🚀 <b>خدمات دیجیتال مارکتینگ AMHR:</b>\n\n"
                "✅ <b>طراحی وب و سئو:</b> وب‌سایت‌های با کارایی بالا برای بازارهای جهانی.\n"
                "✅ <b>دیجیتال مارکتینگ:</b> کمپین‌های استراتژیک برای افزایش بازدهی.\n"
                "✅ <b>ایجنت‌های هوش مصنوعی:</b> طراحی ایجنت‌های AI اختصاصی برای اتوماسیون کسب‌وکار شما."
            )
            msg_ar = (
                "🚀 <b>خدمات AMHR الرقمية:</b>\n\n"
                "✅ <b>تصميم المواقع و SEO:</b> مواقع عالية الأداء للوصول العالمي.\n"
                "✅ <b>التسويق الرقمي:</b> حملات استراتيجية لزيادة العائد على الاستثمار.\n"
                "✅ <b>وكلاء الذكاء الاصطناعي:</b> تصميم وكلاء AI مخصصين لأتمتة أعمالك."
            )
            msg_ru = (
                "🚀 <b>Цифровые услуги AMHR:</b>\n\n"
                "✅ <b>Веб-дизайн и SEO:</b> Высокопроизводительные сайты.\n"
                "✅ <b>Цифровой маркетинг:</b> Стратегические кампании.\n"
                "✅ <b>ИИ-агенты:</b> Разработка пользовательских ИИ-агентов."
            )
            
            content = {"en": msg_en, "fa": msg_fa, "ar": msg_ar, "ru": msg_ru}
            await responder_func(content.get(lang, msg_en), options=get_main_menu_options(lang))

        # --- OPTION 2: ARTIN PLATFORM ---
        elif any(x in text for x in ["Artin", "آرتین", "آرتين", "Артина"]):
            info_text = (
                "🤖 <b>Artin SmartAgent Platform</b>\n"
                "<i>Performance & Modularity Report</i>\n\n"
                "A multi-tenant SaaS solution built on <b>Microservices</b>, <b>FastAPI</b>, and <b>Next.js 14</b>.\n\n"
                "🔹 <b>Core Modules:</b>\n"
                "1️⃣ <b>Artin Expo Smart:</b> For exhibition management.\n"
                "2️⃣ <b>Artin Realty Smart:</b> Real estate automation.\n"
                "3️⃣ <b>Artin Clinic Smart:</b> Healthcare management.\n"
                "4️⃣ <b>Artin Influencer Smart:</b> Campaign orchestration.\n\n"
                "🚀 <b>Key Features:</b>\n"
                "- Secure Integrations (PayPal, Twilio)\n"
                "- Advanced Observability (Grafana, OpenTelemetry)\n"
                "- Full Customer Journey Automation\n\n"
                f"🔗 <b><a href='{WEBSITES[2]}'>Visit Platform Website</a></b>"
            )
            
            # ترجمه خلاصه برای فارسی
            if lang == 'fa':
                info_text = (
                    "🤖 <b>پلتفرم هوشمند Artin SmartAgent</b>\n\n"
                    "یک راهکار SaaS چند مستاجری مبتنی بر <b>Microservices</b> و تکنولوژی‌های مدرن.\n\n"
                    "🔹 <b>ماژول‌های اصلی:</b>\n"
                    "1️⃣ <b>Artin Expo Smart:</b> مدیریت نمایشگاهی.\n"
                    "2️⃣ <b>Artin Realty Smart:</b> اتوماسیون املاک.\n"
                    "3️⃣ <b>Artin Clinic Smart:</b> مدیریت کلینیک.\n"
                    "4️⃣ <b>Artin Influencer Smart:</b> مدیریت کمپین‌ها.\n\n"
                    f"🔗 <b><a href='{WEBSITES[2]}'>مشاهده وبسایت پلتفرم</a></b>"
                )
            
            await responder_func(info_text, options=get_main_menu_options(lang))

        # --- OPTION 3: CEO & CONTACT ---
        elif any(x in text for x in ["CEO", "Contact", "مدیر", "مدير", "تماس", "Контакты"]):
            title = CEO_TITLE.get(lang, CEO_TITLE["en"])
            
            contact_info = (
                f"👤 <b>{CEO_NAME}</b>\n"
                f"<i>{title}</i>\n\n"
                f"📍 <b>Address:</b> {ADDRESS}\n"
                f"🔗 <a href='{MAP_LINK}'>View on Google Maps</a>\n\n"
                f"💼 <b>LinkedIn:</b> <a href='{LINKEDIN_URL}'>View Profile</a>\n\n"
                "🌐 <b>Websites:</b>\n"
                f"• {WEBSITES[0]}\n"
                f"• {WEBSITES[1]}\n"
                f"• {WEBSITES[2]}"
            )
            await responder_func(contact_info, options=get_main_menu_options(lang))

        # --- OPTION 4: BOOKING ---
        elif any(x in text for x in ["Book", "رزرو", "حجز", "Забронировать"]):
            msg = {
                "en": f"📅 <b>Book a Consultation:</b>\nSchedule a meeting with our experts directly via Calendly:\n\n👉 <a href='{BOOKING_URL}'>Click here to Book</a>",
                "fa": f"📅 <b>رزرو مشاوره:</b>\nبرای تنظیم وقت جلسه با متخصصین ما از طریق لینک زیر اقدام کنید:\n\n👉 <a href='{BOOKING_URL}'>برای رزرو کلیک کنید</a>",
                "ar": f"📅 <b>حجز استشارة:</b>\nحدد موعداً مع خبرائنا مباشرة:\n\n👉 <a href='{BOOKING_URL}'>اضغط هنا للحجز</a>",
                "ru": f"📅 <b>Забронировать консультацию:</b>\nЗапишитесь на встречу через Calendly:\n\n👉 <a href='{BOOKING_URL}'>Нажмите здесь</a>"
            }.get(lang, "")
            await responder_func(msg, options=get_main_menu_options(lang))

        # --- OPTION 5: CATALOG ---
        elif any(x in text for x in ["Catalog", "کاتالوگ", "الكتالوج", "Каталог"]):
            msg = {
                "en": f"📥 <b>Download Center:</b>\n\n1. <a href='{CATALOG_URL}'>AMHR Company Services Catalog</a>\n2. <a href='{ARTIN_REPORT_URL}'>Artin SmartAgent Performance Report</a>",
                "fa": f"📥 <b>مرکز دانلود:</b>\n\n1. <a href='{CATALOG_URL}'>کاتالوگ خدمات شرکت AMHR</a>\n2. <a href='{ARTIN_REPORT_URL}'>گزارش عملکرد پلتفرم آرتین</a>",
                "ar": f"📥 <b>مركز التحميل:</b>\n\n1. <a href='{CATALOG_URL}'>كتالوج خدمات AMHR</a>\n2. <a href='{ARTIN_REPORT_URL}'>تقرير أداء منصة آرتين</a>",
                "ru": f"📥 <b>Центр загрузки:</b>\n\n1. <a href='{CATALOG_URL}'>Каталог услуг AMHR</a>\n2. <a href='{ARTIN_REPORT_URL}'>Отчет о платформе Artin</a>"
            }.get(lang, "")
            await responder_func(msg, options=get_main_menu_options(lang))

        else:
            fallback = {
                "en": "Please select an option from the menu.",
                "fa": "لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
                "ar": "الرجاء اختيار خيار من القائمة.",
                "ru": "Пожалуйста, выберите опцию из меню."
            }.get(lang, "Please choose an option.")
            await responder_func(fallback, options=get_main_menu_options(lang))
        return

    # Default Fallback
    await responder_func("Type /start to restart.")

# --- ROUTES ---
@app.get("/")
async def root():
    return {"status": "ok", "message": "AMHR Marketing Bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    
    if not chat_id: return {"ok": True}
    
    async def telegram_responder(resp_text, options=None):
        payload = {
            "chat_id": chat_id, 
            "text": resp_text, 
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if options:
            payload["reply_markup"] = {"keyboard": [[{"text": o}] for o in options], "resize_keyboard": True}
        
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
            except Exception as e:
                print(f"Error sending message: {e}")
                
    await process_user_input(str(chat_id), text, telegram_responder)
    return {"ok": True}

# Endpoint for web integration (optional)
class WebMessage(BaseModel):
    session_id: str
    message: str

@app.post("/web-chat")
async def web_chat(body: WebMessage):
    responses = []
    async def web_responder(resp_text, options=None):
        responses.append({"text": resp_text, "options": options or []})
    await process_user_input(body.session_id, body.message, web_responder)
    return {"messages": responses}
