import os
import telebot
import sqlite3
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

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
    'Еда': ['еда', 'обед', 'ужин', 'завтрак', 'продукты', 'магазин', 'кофе', 'пицца', 'суши', 'бургер'],
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

# ==================== ГЛАВНАЯ КЛАВИАТУРА ====================

def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    
    btn_stats_today = KeyboardButton("📊 Итоги сегодня")
    btn_stats_month = KeyboardButton("📊 Итоги месяц")
    btn_stats_all = KeyboardButton("📊 Итоги всего")
    
    btn_history_today = KeyboardButton("📜 История сегодня")
    btn_history_week = KeyboardButton("📜 История неделя")
    btn_history_month = KeyboardButton("📜 История месяц")
    btn_history_all = KeyboardButton("📜 История всё")
    
    btn_report_today = KeyboardButton("📄 Отчёт сегодня")
    btn_report_week = KeyboardButton("📄 Отчёт неделя")
    btn_report_month = KeyboardButton("📄 Отчёт месяц")
    btn_report_all = KeyboardButton("📄 Отчёт всё")
    
    btn_delete = KeyboardButton("🗑️ Удалить трату")
    btn_clear = KeyboardButton("🗑️ Сбросить всё")
    
    markup.add(btn_stats_today, btn_stats_month, btn_stats_all)
    markup.add(btn_history_today, btn_history_week, btn_history_month, btn_history_all)
    markup.add(btn_report_today, btn_report_week, btn_report_month, btn_report_all)
    markup.add(btn_delete, btn_clear)
    
    return markup

# ==================== КЛАВИАТУРА УДАЛЕНИЯ ====================

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

# ==================== ИТОГИ ====================

@bot.message_handler(func=lambda message: message.text == "📊 Итоги сегодня")
def stats_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    show_stats(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📊 Итоги месяц")
def stats_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    show_stats(message, month_ago, "За месяц")

@bot.message_handler(func=lambda message: message.text == "📊 Итоги всего")
def stats_all(message):
    show_stats(message, "1900-01-01", "За всё время")

def show_stats(message, date_from, period_name):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(amount) FROM expenses WHERE date >= ?', (date_from,))
    total = cursor.fetchone()[0]
    if total is None: total = 0
    cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category', (date_from,))
    categories = cursor.fetchall()
    conn.close()

    text = f"💰 Итог ({period_name}): {total:.2f} ₽\n\n"
    text += "📊 По категориям:\n"
    categories.sort(key=lambda x: x[1] or 0, reverse=True)
    for cat, amount in categories:
        text += f"▫️ {cat}: {amount:.2f} ₽\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())

# ==================== ИСТОРИЯ ====================

@bot.message_handler(func=lambda message: message.text == "📜 История сегодня")
def history_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    show_history(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📜 История неделя")
def history_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    show_history(message, week_ago, "За неделю")

@bot.message_handler(func=lambda message: message.text == "📜 История месяц")
def history_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    show_history(message, month_ago, "За месяц")

@bot.message_handler(func=lambda message: message.text == "📜 История всё")
def history_all(message):
    show_history(message, "1900-01-01", "За всё время")

def show_history(message, date_from, period_name):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, id FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        bot.send_message(message.chat.id, f"📜 История ({period_name}):\n\nЗаписей не найдено.", reply_markup=create_main_keyboard())
        return
    
    text = f"📜 История ({period_name}):\n\n"
    total = 0
    for exp in expenses:
        amount, desc, cat, id_ = exp
        total += amount
        text += f"• {amount:.2f} ₽ — {desc} ({cat})\n"
    
    text += f"\n💰 Итого: {total:.2f} ₽"
    bot.send_message(message.chat.id, text, reply_markup=create_main_keyboard())

# ==================== ОТЧЁТ ====================

@bot.message_handler(func=lambda message: message.text == "📄 Отчёт сегодня")
def report_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    send_report(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📄 Отчёт неделя")
def report_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    send_report(message, week_ago, "За неделю")

@bot.message_handler(func=lambda message: message.text == "📄 Отчёт месяц")
def report_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    send_report(message, month_ago, "За месяц")

@bot.message_handler(func=lambda message: message.text == "📄 Отчёт всё")
def report_all(message):
    send_report(message, "1900-01-01", "За всё время")

def send_report(message, date_from, period_name):
    bot.send_message(message.chat.id, "⏳ Генерирую отчёт...", reply_markup=create_main_keyboard())
    
    try:
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('SELECT amount, description, category, date FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
        expenses = cursor.fetchall()
        cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category', (date_from,))
        categories = cursor.fetchall()
        conn.close()
        
        if not expenses:
            bot.send_message(message.chat.id, "❌ Нет данных за этот период.", reply_markup=create_main_keyboard())
            return
        
        total = sum(e[0] for e in expenses)
        
        text = f"📊 **{period_name}**\n\n"
        text += f"💰 **Общая сумма: {total:.2f} ₽**\n\n"
        text += "📈 **По категориям:**\n"
        
        for cat, amount in categories:
            percent = (amount / total) * 100
            bar = "▓" * int(percent / 5) + "░" * (20 - int(percent / 5))
            text += f"{cat}: {amount:.2f} ₽ ({percent:.1f}%)\n{bar}\n\n"
        
        text += "📝 **Последние траты:**\n"
        for exp in expenses[:15]:
            text += f"• {exp[0]:.2f} ₽ — {exp[1]} ({exp[2]})\n"
        
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}", reply_markup=create_main_keyboard())

# ==================== УДАЛЕНИЕ ====================

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
    
    text = "🗑️ Выбери запись для удаления:\n"
    markup = create_delete_keyboard(expenses)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_expense(call):
    try:
        expense_id = int(call.data.split('_')[1])
        
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ Запись удалена!")
        bot.send_message(call.message.chat.id, "✅ Запись удалена!", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

# ==================== СБРОС ====================

@bot.message_handler(func=lambda message: message.text == "🗑️ Сбросить всё")
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
    ignore_list = [
        "📊 Итоги сегодня", "📊 Итоги месяц", "📊 Итоги всего",
        "📜 История сегодня", "📜 История неделя", "📜 История месяц", "📜 История всё",
        "📄 Отчёт сегодня", "📄 Отчёт неделя", "📄 Отчёт месяц", "📄 Отчёт всё",
        "🗑️ Удалить трату", "🗑️ Сбросить всё"
    ]
    
    if message.text in ignore_list:
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
        bot.reply_to(message, "❌ Ошибка! Пиши: сумма описание\nПример: 500 такси", 
                     reply_markup=create_main_keyboard())

# ==================== ЗАПУСК ====================

print("✅ Бот запущен!")
bot.infinity_polling()
