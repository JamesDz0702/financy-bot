import os
import telebot
import sqlite3
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

bot = telebot.TeleBot(API_TOKEN)

def init_db():
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            description TEXT,
            category TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

CATEGORY_KEYWORDS = {
    'Еда': ['еда', 'обед', 'ужин', 'завтрак', 'продукты', 'магазин', 'кофе'],
    'Транспорт': ['такси', 'метро', 'автобус', 'бензин', 'машина'],
    'Дом': ['аренда', 'коммуналка', 'интернет', 'ремонт'],
    'Развлечения': ['кино', 'бар', 'клуб', 'подписка'],
    'Здоровье': ['аптека', 'врач', 'лекарства'],
    'Связь': ['телефон', 'мтс', 'билайн'],
}

def get_category(text):
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return 'Разное'

def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_stats = KeyboardButton("📊 Посмотреть итоги")
    btn_clear = KeyboardButton("🗑️ Сбросить данные")
    markup.add(btn_stats, btn_clear)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "Привет! Я твой финансовый помощник 💰\n\n"
                 "📌 Просто напиши сумму и описание:\n"
                 "`500 обед`\n"
                 "`1200 такси`\n\n"
                 "Или используй кнопки ниже 👇",
                 reply_markup=create_main_keyboard(),
                 parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == "📊 Посмотреть итоги")
def show_stats_button(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(amount) FROM expenses')
    total = cursor.fetchone()[0]
    if total is None: total = 0
    cursor.execute('SELECT category, SUM(amount) FROM expenses GROUP BY category')
    categories = cursor.fetchall()
    conn.close()
    text = f"Общий итог: {total:.2f} ₽\n\n**По категориям:**\n"
    categories.sort(key=lambda x: x[1] or 0, reverse=True)
    for cat, amount in categories:
        text += f"▫️ {cat}: {amount:.2f} ₽\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🗑️ Сбросить данные")
def clear_all_button(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses')
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Все записи удалены!", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    if message.text in ["📊 Посмотреть итоги", "🗑️ Сбросить данные"]:
        return
    try:
        text = message.text.strip()
        parts = text.split()
        amount = float(parts[0])
        description = " ".join(parts[1:]) if len(parts) > 1 else "Без описания"
        category = get_category(description)
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO expenses (amount, description, category, date) VALUES (?, ?, ?, ?)',
                       (amount, description, category, date_now))
        conn.commit()
        conn.close()
        bot.reply_to(message, 
                     f"✅ Записал: *{amount:.2f} ₽*\nКатегория: `{category}`", 
                     parse_mode='Markdown',
                     reply_markup=create_main_keyboard())
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка! Пиши: сумма описание\nПример: `500 такси`", 
                     reply_markup=create_main_keyboard())

print("Running bot...")
bot.infinity_polling()
