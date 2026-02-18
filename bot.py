import os
import telebot
import sqlite3
import time
import threading
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
    '🍔 Еда': ['еда', 'обед', 'ужин', 'завтрак', 'продукты', 'магазин', 'кофе', 'пицца', 'суши', 'бургер'],
    '🚕 Транспорт': ['такси', 'метро', 'автобус', 'бензин', 'машина', 'uber', 'bolt'],
    '🏠 Дом': ['аренда', 'коммуналка', 'интернет', 'ремонт', 'мебель'],
    '🎬 Развлечения': ['кино', 'бар', 'клуб', 'подписка', 'игры', 'концерт'],
    '💊 Здоровье': ['аптека', 'врач', 'лекарства', 'стоматолог', 'спортзал'],
    '📱 Связь': ['телефон', 'мтс', 'билайн', 'мегафон'],
    '🛍️ Покупки': ['одежда', 'обувь', 'техника', 'подарок'],
}

def get_category(text):
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return category
    return '📦 Разное'

# ==================== КЛАВИАТУРЫ ====================

def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(KeyboardButton("📊 Итоги"), KeyboardButton("📜 История"))
    markup.add(KeyboardButton("🗑️ Удалить"), KeyboardButton("🗑️ Сбросить"))
    return markup

def create_period_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Неделя"))
    markup.add(KeyboardButton("📆 Месяц"), KeyboardButton("📋 Всё"))
    markup.add(KeyboardButton("🔙 Назад"))
    return markup

def create_delete_keyboard(expenses):
    markup = InlineKeyboardMarkup()
    for exp in expenses:
        btn = InlineKeyboardButton(
            f"❌ {exp[0]} ₽ — {exp[1]}",
            callback_data=f"del_{exp[3]}"
        )
        markup.add(btn)
    return markup

# ==================== АВТОУДАЛЕНИЕ ====================

def delete_later(chat_id, message_id, delay=10):
    def _delete():
        try:
            time.sleep(delay)
            bot.delete_message(chat_id, message_id)
        except:
            pass
    threading.Thread(target=_delete, daemon=True).start()

# ==================== КОМАНДЫ ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
💰 *Добро пожаловать!*

Я помогу тебе учитывать траты.

📝 *Как пользоваться:*
• Просто напиши сумму и описание
• Пример: `500 обед` или `150 такси`

📌 *Команды:*
• /start — перезапустить
• /help — помощь
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=create_main_keyboard())

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
📖 *Помощь:*

Добавление траты:
`500 кофе` → добавит 500 ₽ (категория Еда)

Кнопки:
📊 Итоги — посмотреть общую сумму
📜 История — история за период
🗑️ Удалить — удалить запись
🗑️ Сбросить — удалить всё
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔙 Назад")
def go_back(message):
    bot.send_message(message.chat.id, "Выбери действие:", reply_markup=create_main_keyboard())

# ==================== ИТОГИ ====================

@bot.message_handler(func=lambda message: message.text == "📊 Итоги")
def show_stats(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(amount) FROM expenses')
    total = cursor.fetchone()[0] or 0
    cursor.execute('SELECT category, SUM(amount) FROM expenses GROUP BY category ORDER BY SUM(amount) DESC')
    categories = cursor.fetchall()
    conn.close()

    if total == 0:
        bot.send_message(message.chat.id, "📊 Пока нет трат 🤷", reply_markup=create_main_keyboard())
        return

    text = f"💰 *Итого: {total:.2f} ₽*\n\n"
    text += "*По категориям:*\n"
    
    for cat, amount in categories:
        percent = (amount / total) * 100
        bar = "▓" * int(percent / 5)
        text += f"{cat}: {amount:.2f} ₽\n{bar} {percent:.0f}%\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())

# ==================== ИСТОРИЯ ====================

@bot.message_handler(func=lambda message: message.text == "📜 История")
def history_menu(message):
    bot.send_message(message.chat.id, "📜 Выбери период:", reply_markup=create_period_keyboard())

@bot.message_handler(func=lambda message: message.text == "📅 Сегодня")
def history_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    show_history(message, today, "Сегодня")

@bot.message_handler(func=lambda message: message.text == "📆 Неделя")
def history_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    show_history(message, week_ago, "Неделя")

@bot.message_handler(func=lambda message: message.text == "📆 Месяц")
def history_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    show_history(message, month_ago, "Месяц")

@bot.message_handler(func=lambda message: message.text == "📋 Всё")
def history_all(message):
    show_history(message, "1900-01-01", "Всё время")

def show_history(message, date_from, period_name):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, id FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        bot.send_message(message.chat.id, f"📜 Нет записей за {period_name} 😔", reply_markup=create_period_keyboard())
        return
    
    text = f"📜 *История за {period_name}:*\n\n"
    total = 0
    for exp in expenses:
        amount, desc, cat, id_ = exp
        total += amount
        text += f"• {amount:.2f} ₽ — {desc} {cat}\n"
    
    text += f"\n💰 *Итого: {total:.2f} ₽*"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_period_keyboard())

# ==================== УДАЛЕНИЕ ====================

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить")
def delete_menu(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('SELECT amount, description, category, id FROM expenses ORDER BY id DESC LIMIT 10')
    expenses = cursor.fetchall()
    conn.close()
    
    if not expenses:
        bot.send_message(message.chat.id, "Нет записей для удаления 🤷", reply_markup=create_main_keyboard())
        return
    
    text = "🗑️ *Выбери запись:*\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_delete_keyboard(expenses))

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_expense(call):
    try:
        expense_id = int(call.data.split('_')[1])
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "✅ Удалено!")
        delete_later(call.message.chat_id, call.message.message_id, delay=5)
        bot.send_message(call.message.chat_id, "✅ Запись удалена!", reply_markup=create_main_keyboard())
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {str(e)}")

# ==================== СБРОС ====================

@bot.message_handler(func=lambda message: message.text == "🗑️ Сбросить")
def clear_all(message):
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses')
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "🗑️ Все записи удалены!", reply_markup=create_main_keyboard())

# ==================== ДОБАВЛЕНИЕ ТРАТ ====================

@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    ignore_list = ["📊 Итоги", "📜 История", "🗑️ Удалить", "🗑️ Сбросить",
                   "📅 Сегодня", "📆 Неделя", "📆 Месяц", "📋 Всё", "🔙 Назад"]
    
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
        
        # Подтверждение и автоудаление
        msg = bot.reply_to(message, f"✅ *Добавлено:* {amount:.2f} ₽\n{category}", 
                     parse_mode='Markdown', reply_markup=create_main_keyboard())
        
        delete_later(message.chat_id, message.message_id, delay=10)
        delete_later(message.chat_id, msg.message_id, delay=10)
        
    except:
        pass  # Игнорируем ошибки (не трата)

# ==================== ЗАПУСК ====================

print("✅ Бот запущен!")
bot.infinity_polling()
