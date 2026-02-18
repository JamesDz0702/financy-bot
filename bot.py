import telebot
import sqlite3
import os
from datetime import datetime
from telebot import types

# Токен берётся из переменных окружения Railway
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

bot = telebot.TeleBot(API_TOKEN)

# --- База данных ---
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

# --- Категории ---
CATEGORY_KEYWORDS = {
    'Еда': ['еда', 'обед', 'ужин', 'завтрак', 'продукты', 'магазин', 'кофе', 'бургер'],
    'Транспорт': ['такси', 'метро', 'автобус', 'бензин', 'машина', 'uber'],
    'Дом': ['аренда', 'коммуналка', 'интернет', 'ремонт', 'мебель'],
    'Здоровье': ['аптека', 'врач', 'лекарства', 'спортзал'],
    'Развлечения': ['кино', 'театр', 'подписка', 'игры', 'бар'],
    'Связь': ['телефон', 'мтс', 'билайн', 'мегафон'],
}

def get_category(text):
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return 'Разное'

# --- Кнопки ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_stats = types.KeyboardButton('📊 Статистика')
    btn_history = types.KeyboardButton('📜 История')
    btn_clear = types.KeyboardButton('🗑️ Очистить')
    btn_help = types.KeyboardButton('❓ Помощь')
    markup.add(btn_stats, btn_history)
    markup.add(btn_clear, btn_help)
    return markup

# --- Команда /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
                 "Привет! Я бот-бухгалтер.\n\n"
                 "Напиши сумму и описание:\n👉 500 обед\n\n"
                 "Используй кнопки внизу 👇",
                 reply_markup=main_menu())

# --- Показать статистику ---
def show_stats(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()

    cursor.execute('SELECT SUM(amount) FROM expenses')
    total = cursor.fetchone()[0]
    if total is None:
        total = 0

    cursor.execute('SELECT category, SUM(amount) FROM expenses GROUP BY category')
    categories = cursor.fetchall()
    conn.close()

    text = "💰 Общий итог: {} руб.\n\nПо категориям:\n".format(total)

    categories.sort(key=lambda x: x[1], reverse=True)

    for cat, amount in categories:
        text += "▫️ {}: {} руб.\n".format(cat, amount)

    bot.reply_to(message, text)

# --- Кнопка Статистика ---
@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def stats_button(message):
    show_stats(message)

# --- Показать историю ---
def show_history(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category FROM expenses ORDER BY id DESC LIMIT 5')
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.reply_to(message, "История пуста.")
        return

    text = "📜 Последние траты:\n\n"
    for row in rows:
        text += "{} руб. - {} ({})\n".format(row[0], row[1], row[2])
    bot.reply_to(message, text)

# --- Кнопка История ---
@bot.message_handler(func=lambda message: message.text == '📜 История')
def history_button(message):
    show_history(message)

# --- Очистка с подтверждением ---
@bot.message_handler(func=lambda message: message.text == '🗑️ Очистить')
def clear_button(message):
    markup = types.InlineKeyboardMarkup()
    btn_yes = types.InlineKeyboardButton('✅ Да, очистить', callback_data='clear_yes')
    btn_no = types.InlineKeyboardButton('❌ Отмена', callback_data='clear_no')
    markup.add(btn_yes, btn_no)
    bot.reply_to(message, "⚠️ Уверены? Это удалит всю историю!", reply_markup=markup)

# --- Обработка подтверждения ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('clear_'))
def clear_callback(call):
    if call.data == 'clear_yes':
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses')
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "История очищена!")
        bot.edit_message_text("✅ История очищена!", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Отменено")
        bot.edit_message_text("❌ Очистка отменена", call.message.chat.id, call.message.message_id)

# --- Кнопка Помощь ---
@bot.message_handler(func=lambda message: message.text == '❓ Помощь')
def help_button(message):
    bot.reply_to(message,
                 "Как пользоваться:\n\n"
                 "1. Напиши сумму и описание: 500 обед\n"
                 "2. Бот определит категорию автоматически\n"
                 "3. Нажми Статистика для просмотра итогов\n\n"
                 "Команды:\n"
                 "/start - главное меню\n"
                 "/stats - статистика\n"
                 "/history - история\n"
                 "/clear - очистить")

# --- Команда /stats ---
@bot.message_handler(commands=['stats'])
def stats_command(message):
    show_stats(message)

# --- Команда /history ---
@bot.message_handler(commands=['history'])
def history_command(message):
    show_history(message)

# --- Команда /clear ---
@bot.message_handler(commands=['clear'])
def clear_command(message):
    clear_button(message)

# --- Обработка трат ---
@bot.message_handler(func=lambda message: message.text not in ['📊 Статистика', '📜 История', '🗑️ Очистить', '❓ Помощь'])
def handle_expense(message):
    try:
        text = message.text.strip()
        parts = text.split()
        amount = float(parts[0])
        description = " ".join(parts[1:]) if len(parts) > 1 else "Без описания"
        category = get_category(description)
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO expenses (amount, description, category, date) 
