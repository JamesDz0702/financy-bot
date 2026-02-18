import os
import telebot
import sqlite3
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import matplotlib.pyplot as plt
from io import BytesIO

API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# ==================== БАЗА ДАННЫХ ====================

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

# ==================== КАТЕГОРИИ ====================

CATEGORY_KEYWORDS = {
    'Еда': ['еда', 'обед', 'ужин', 'завтрак', 'продукты', 'магазин', 'кофе', 'пицца', 'суши'],
    'Транспорт': ['такси', 'метро', 'автобус', 'бензин', 'машина', 'uber', 'bolt'],
    'Дом': ['аренда', 'коммуналка', 'интернет', 'ремонт', 'мебель'],
    'Развлечения': ['кино', 'бар', 'клуб', 'подписка', 'игры', 'концерт'],
    'Здоровье': ['аптека', 'врач', 'лекарства', 'стоматолог', 'спортзал'],
    'Связь': ['телефон', 'мтс', 'билайн', 'мегафон'],
    'Покупки': ['одежда', 'обувь', 'техника', 'подарок'],
}

def get_category(text):
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return 'Разное'

# ==================== КЛАВИАТУРЫ ====================

def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_stats = KeyboardButton("📊 Посмотреть итоги")
    btn_history = KeyboardButton("📜 История")
    btn_pdf = KeyboardButton("📄 PDF-отчёт")
    btn_delete = KeyboardButton("🗑️ Удалить трату")
    btn_clear = KeyboardButton("🗑️ Сбросить данные")
    markup.add(btn_stats, btn_history)
    markup.add(btn_pdf, btn_delete)
    markup.add(btn_clear)
    return markup

def create_history_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📅 За сегодня"), KeyboardButton("📆 За неделю"))
    markup.add(KeyboardButton("📆 За месяц"), KeyboardButton("📋 За всё время"))
    markup.add(KeyboardButton("🔙 Назад"))
    return markup

def create_period_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📅 За сегодня"), KeyboardButton("📆 За неделю"))
    markup.add(KeyboardButton("📆 За месяц"), KeyboardButton("📋 За всё время"))
    markup.add(KeyboardButton("🔙 Назад"))
    return markup

def create_delete_keyboard(expenses):
    markup = InlineKeyboardMarkup()
    for exp in expenses:
        btn = InlineKeyboardButton(
            f"❌ {exp[0]} ₽ - {exp[1]} ({exp[2]})",
            callback_data=f"delete_{exp[3]}"
        )
        markup.add(btn)
    return markup

# ==================== КОМАНДЫ ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
                 "👋 Привет! Я твой финансовый помощник 💰\n\n"
                 "📌 Просто напиши сумму и описание:\n"
                 "`500 обед`\n"
                 "`1200 такси`\n\n"
                 "Используй кнопки ниже 👇",
                 reply_markup=create_main_keyboard(),
                 parse_mode='Markdown')

# Обработка кнопки "Назад"
@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def go_back(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=create_main_keyboard())

# ==================== ИСТОРИЯ ====================

@bot.message_handler(func=lambda message: message.text == "📜 История")
def history_menu(message):
    bot.send_message(message.chat.id, "📜 Выбери период:", reply_markup=create_history_keyboard())

@bot.message_handler(func=lambda message: message.text == "📅 За сегодня")
def history_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    show_history(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📆 За неделю")
def history_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    show_history(message, week_ago, "За последние 7 дней")

@bot.message_handler(func=lambda message: message.text == "📆 За месяц")
def history_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    show_history(message, month_ago, "За последние 30 дней")

@bot.message_handler(func=lambda message: message.text == "📋 За всё время")
def history_all(message):
    show_history(message, "1900-01-01", "За всё время")

def show_history(message, date_from, period_name):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, id FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        bot.send_message(message.chat.id, f"📜 История ({period_name}):\n\nЗаписей не найдено.", reply_markup=create_history_keyboard())
        return
    
    text = f"📜 История ({period_name}):\n\n"
    total = 0
    for exp in expenses:
        amount, desc, cat, id_ = exp
        total += amount
        text += f"• {amount:.2f} ₽ — {desc} ({cat})\n"
    
    text += f"\n💰 Итого: {total:.2f} ₽"
    bot.send_message(message.chat.id, text, reply_markup=create_history_keyboard())

# ==================== PDF-ОТЧЁТ ====================

@bot.message_handler(func=lambda message: message.text == "📄 PDF-отчёт")
def pdf_menu(message):
    bot.send_message(message.chat.id, "📄 Выбери период для отчёта:", reply_markup=create_period_keyboard())

def generate_chart_and_report(date_from, period_name):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, date FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
    expenses = cursor.fetchall()
    cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category', (date_from,))
    categories = cursor.fetchall()
    conn.close()
    
    if not expenses:
        return None, None
    
    # Создаём график
    labels = [c[0] for c in categories]
    values = [c[1] for c in categories]
    
    plt.figure(figsize=(8, 6))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
    plt.title(f'Траты ({period_name})')
    
    # Сохраняем график в память
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight')
    img_buffer.seek(0)
    plt.close()
    
    # Создаём текст отчёта
    total = sum(e[0] for e in expenses)
    text = f"📄 **{period_name}**\n\n"
    text += f"💰 *Общая сумма: {total:.2f} ₽*\n\n"
    text += "*По категориям:*\n"
    for cat, amount in categories:
        text += f"• {cat}: {amount:.2f} ₽\n"
    
    text += "\n*Детализация:*\n"
    for exp in expenses:
        text += f"• {exp[0]:.2f} ₽ — {exp[1]} ({exp[3]})\n"
    
    return img_buffer, text

@bot.message_handler(func=lambda message: message.text == "📅 За сегодня")
def pdf_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    send_pdf_report(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📆 За неделю")
def pdf_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    send_pdf_report(message, week_ago, "За неделю")

@bot.message_handler(func=lambda message: message.text == "📆 За месяц")
def pdf_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    send_pdf_report(message, month_ago, "За месяц")

@bot.message_handler(func=lambda message: message.text == "📋 За всё время")
def pdf_all(message):
    send_pdf_report(message, "1900-01-01", "За всё время")

def send_pdf_report(message, date_from, period_name):
    img_buffer, text = generate_chart_and_report(date_from, period_name)
    
    if img_buffer is None:
        bot.send_message(message.chat.id, "Нет данных за выбранный период.", reply_markup=create_period_keyboard())
        return
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_period_keyboard())
    bot.send_photo(message.chat.id, img_buffer, reply_markup=create_period_keyboard())

# ==================== УДАЛЕНИЕ ТРАТ ====================

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить трату")
def delete_menu(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, id FROM expenses ORDER BY id DESC LIMIT 10')
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        bot.send_message(message.chat.id, "Нет записей для удаления.", reply_markup=create_main_keyboard())
        return
    
    text = "🗑️ Выбери запись для удаления:\n\n"
    markup = create_delete_keyboard(expenses)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_expense(call):
    expense_id = int(call.data.split('_')[1])
    
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Запись удалена!")
    bot.send_message(call.message.chat.id, "✅ Запись удалена. Выбери ещё:", reply_markup=create_main_keyboard())

# ==================== ИТОГИ ====================

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

    text = f"💰 Общий итог: {total:.2f} ₽\n\nПо категориям:\n"
    categories.sort(key=lambda x: x[1] or 0, reverse=True)
    for cat, amount in categories:
        text += f"▫️ {cat}: {amount:.2f} ₽\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())

# ==================== СБРОС ====================

@bot.message_handler(func=lambda message: message.text == "🗑️ Сбросить данные")
def clear_all_button(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses')
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "🗑️ Все записи удалены!", reply_markup=create_main_keyboard())

# ==================== ДОБАВЛЕНИЕ ТРАТ ====================

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    if message.text in ["📊 Посмотреть итоги", "📜 История", "📄 PDF-отчёт", 
