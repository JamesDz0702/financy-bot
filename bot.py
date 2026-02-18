import os
import telebot
import sqlite3
import io
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

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

init_db()

# --- Категории ---
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

# --- Список всех кнопок (чтобы не дублировать) ---
ALL_BUTTONS = [
    "📊 Статистика",
    "📜 История трат",
    "❌ Удалить трату",
    "📄 PDF отчёт",
    "🗑️ Сбросить данные",
    "❓ Помощь"
]

# --- Главная клавиатура ---
def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    btn_stats    = KeyboardButton("📊 Статистика")
    btn_history  = KeyboardButton("📜 История трат")
    btn_delete   = KeyboardButton("❌ Удалить трату")
    btn_pdf      = KeyboardButton("📄 PDF отчёт")
    btn_clear    = KeyboardButton("🗑️ Сбросить данные")
    btn_help     = KeyboardButton("❓ Помощь")
    markup.add(btn_stats, btn_history)
    markup.add(btn_delete, btn_pdf)
    markup.add(btn_clear, btn_help)
    return markup

# --- Клавиатура выбора периода ---
def create_period_keyboard(action):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 Сегодня",    callback_data=f"{action}_today"),
        InlineKeyboardButton("📅 Неделя",     callback_data=f"{action}_week"),
        InlineKeyboardButton("📅 Месяц",      callback_data=f"{action}_month"),
        InlineKeyboardButton("📅 Всё время",  callback_data=f"{action}_all")
    )
    return markup

# --- Получить диапазон дат ---
def get_date_range(period):
    now = datetime.now()
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0)
        return start.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M"), "Сегодня"
    elif period == 'week':
        start = now - timedelta(days=7)
        return start.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M"), "За неделю"
    elif period == 'month':
        start = now - timedelta(days=30)
        return start.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d %H:%M"), "За месяц"
    else:
        return "2000-01-01 00:00", now.strftime("%Y-%m-%d %H:%M"), "За всё время"

# --- Получить траты за период ---
def get_expenses_by_period(period):
    start, end, label = get_date_range(period)
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, amount, description, category, date FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC',
        (start, end)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows, label

# --- Создать PDF ---
@bot.message_handler(func=lambda message: message.text == "📄 PDF сегодня")
def pdf_today(message):
    today = datetime.now().strftime("%Y-%m-%d")
    send_pdf_report(message, today, "За сегодня")

@bot.message_handler(func=lambda message: message.text == "📄 PDF неделя")
def pdf_week(message):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    send_pdf_report(message, week_ago, "За неделю")

@bot.message_handler(func=lambda message: message.text == "📄 PDF месяц")
def pdf_month(message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    send_pdf_report(message, month_ago, "За месяц")

@bot.message_handler(func=lambda message: message.text == "📄 PDF всё")
def pdf_all(message):
    send_pdf_report(message, "1900-01-01", "За всё время")

def generate_chart(date_from, period_name):
    try:
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('SELECT amount, description, category, date FROM expenses WHERE date >= ? ORDER BY id DESC', (date_from,))
        expenses = cursor.fetchall()
        cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE date >= ? GROUP BY category', (date_from,))
        categories = cursor.fetchall()
        conn.close()
        
        if not expenses or not categories:
            return None, "Нет данных за этот период", 0
        
        # График
        labels = [c[0] for c in categories]
        values = [c[1] for c in categories]
        
        plt.figure(figsize=(8, 6))
        
        # Используем разные цвета
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors[:len(values)])
        plt.title(f'Траты ({period_name})', fontsize=14, fontweight='bold')
        
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', facecolor='#1a1a2e')
        plt.close()
        
        img_buffer.seek(0)
        
        # Текст
        total = sum(e[0] for e in expenses)
        text = f"📄 **{period_name}**\n\n"
        text += f"💰 *Общая сумма: {total:.2f} ₽*\n\n"
        text += "*По категориям:*\n"
        for cat, amount in categories:
            text += f"• {cat}: {amount:.2f} ₽\n"
        
        return img_buffer, text, total
        
    except Exception as e:
        print(f"Ошибка при генерации графика: {e}")
        return None, f"Ошибка: {str(e)}", 0

def send_pdf_report(message, date_from, period_name):
    # Сначала отправляем сообщение о начале генерации
    bot.send_message(message.chat.id, "⏳ Генерирую отчёт, подожди...", reply_markup=create_main_keyboard())
    
    img_buffer, text, total = generate_chart(date_from, period_name)
    
    if img_buffer is None:
        bot.send_message(message.chat.id, f"❌ {text}", reply_markup=create_main_keyboard())
        return
    
    try:
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=create_main_keyboard())
        bot.send_photo(message.chat.id, img_buffer, reply_markup=create_main_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при отправке: {str(e)}", reply_markup=create_main_keyboard())

    # Заголовок
    story.append(Paragraph("Финансовый отчёт",
        ParagraphStyle('T', parent=styles['Title'], fontSize=22,
                       spaceAfter=10, textColor=colors.HexColor('#2C3E50'))))

    story.append(Paragraph(
        f"{label} | Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        ParagraphStyle('S', parent=styles['Normal'], fontSize=12,
                       spaceAfter=10, textColor=colors.HexColor('#7F8C8D'))))

    story.append(Paragraph(f"Общая сумма: {total:.2f} руб.",
        ParagraphStyle('Tot', parent=styles['Normal'], fontSize=18,
                       spaceAfter=20, textColor=colors.HexColor('#27AE60'),
                       fontName='Helvetica-Bold')))

    story.append(Spacer(1, 10))

    # Таблица категорий
    story.append(Paragraph("По категориям:",
        ParagraphStyle('Sec', parent=styles['Heading2'], fontSize=14,
                       textColor=colors.HexColor('#2C3E50'), spaceAfter=10)))

    tdata = [['Категория', 'Сумма (руб.)', 'Доля (%)']]
    for cat, amt in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        tdata.append([cat, f"{amt:.2f}", f"{(amt / total * 100):.1f}%"])
    tdata.append(['ИТОГО', f"{total:.2f}", "100%"])

    t = Table(tdata, colWidths=[200, 150, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0),  (-1, 0),  colors.HexColor('#2C3E50')),
        ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0),  (-1, -1), 11),
        ('ALIGN',         (0, 0),  (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -2), [colors.white, colors.HexColor('#ECF0F1')]),
        ('BACKGROUND',    (0, -1), (-1, -1), colors.HexColor('#27AE60')),
        ('TEXTCOLOR',     (0, -1), (-1, -1), colors.white),
        ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID',          (0, 0),  (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT',     (0, 0),  (-1, -1), 28),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # Текстовый график
    story.append(Paragraph("Визуализация:",
        ParagraphStyle('Sec2', parent=styles['Heading2'], fontSize=14,
                       textColor=colors.HexColor('#2C3E50'), spaceAfter=10)))

    max_amt = max(categories.values())
    bar_data = []
    for cat, amt in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        bar_len = int((amt / max_amt) * 20)
        bar = '█' * bar_len + '░' * (20 - bar_len)
        pct = (amt / total * 100)
        bar_data.append([cat, bar, f"{amt:.2f} руб.", f"{pct:.1f}%"])

    bar_table = Table(bar_data, colWidths=[100, 160, 120, 70])
    bar_table.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',  (0, 0), (-1, -1), 10),
        ('ALIGN',     (0, 0), (0, -1),  'LEFT'),
        ('ALIGN',     (1, 0), (1, -1),  'LEFT'),
        ('ALIGN',     (2, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (1, 0), (1, -1),  colors.HexColor('#2688eb')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('ROWHEIGHT', (0, 0), (-1, -1), 22),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(bar_table)
    story.append(Spacer(1, 20))

    # Детализация
    story.append(Paragraph("Все траты:",
        ParagraphStyle('Sec3', parent=styles['Heading2'], fontSize=14,
                       textColor=colors.HexColor('#2C3E50'), spaceAfter=10)))

    ddata = [['#', 'Дата', 'Описание', 'Категория', 'Сумма']]
    for i, row in enumerate(rows, 1):
        ddata.append([str(i), row[4][:10], row[2][:25], row[3], f"{row[1]:.2f}"])

    dt = Table(ddata, colWidths=[25, 80, 170, 100, 75])
    dt.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0),  (-1, 0),  colors.HexColor('#34495E')),
        ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0),  (-1, -1), 9),
        ('ALIGN',         (0, 0),  (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS',(0, 1),  (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ('GRID',          (0, 0),  (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT',     (0, 0),  (-1, -1), 20),
    ]))
    story.append(dt)

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf

    # --- Графики ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('#f8f9fa')

    cat_names  = list(categories.keys())
    cat_values = list(categories.values())
    colors_list = ['#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD']

    # Круговая диаграмма
    ax1.pie(cat_values, labels=cat_names, autopct='%1.1f%%',
            colors=colors_list[:len(cat_names)], startangle=90)
    ax1.set_title(f'Распределение трат\n{label}', fontsize=14, fontweight='bold', pad=20)

    # Столбчатая диаграмма
    bars = ax2.bar(cat_names, cat_values, color=colors_list[:len(cat_names)], width=0.6)
    ax2.set_title(f'Суммы по категориям\n{label}', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Сумма (руб.)', fontsize=12)
    ax2.set_facecolor('#f8f9fa')

    for bar, value in zip(bars, cat_values):
        ax2.text(bar.get_x() + bar.get_width() / 2.,
                 bar.get_height() + max(cat_values) * 0.01,
                 f'{value:.0f} руб.',
                 ha='center', va='bottom', fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    chart_buffer = io.BytesIO()
    plt.savefig(chart_buffer, format='png', dpi=150, bbox_inches='tight')
    chart_buffer.seek(0)
    plt.close()

    # --- PDF ---
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                            rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=20,
                                 spaceAfter=10, textColor=colors.HexColor('#2C3E50'))
    sub_style   = ParagraphStyle('S', parent=styles['Normal'], fontSize=12,
                                 spaceAfter=20, textColor=colors.HexColor('#7F8C8D'))
    total_style = ParagraphStyle('Tot', parent=styles['Normal'], fontSize=16,
                                 spaceAfter=20, textColor=colors.HexColor('#27AE60'),
                                 fontName='Helvetica-Bold')
    section_style = ParagraphStyle('Sec', parent=styles['Heading2'], fontSize=14,
                                   textColor=colors.HexColor('#2C3E50'), spaceAfter=10)

    story.append(Paragraph("Финансовый отчёт", title_style))
    story.append(Paragraph(f"{label} | Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}", sub_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Общая сумма трат: {total:.2f} руб.", total_style))
    story.append(Spacer(1, 10))

    # Таблица категорий
    table_data = [['Категория', 'Сумма (руб.)', 'Доля (%)']]
    for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        percent = (amount / total * 100) if total > 0 else 0
        table_data.append([cat, f"{amount:.2f}", f"{percent:.1f}%"])
    table_data.append(['ИТОГО', f"{total:.2f}", "100%"])

    t = Table(table_data, colWidths=[200, 150, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),  (-1,0),  colors.HexColor('#2C3E50')),
        ('TEXTCOLOR',     (0,0),  (-1,0),  colors.white),
        ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),  (-1,-1), 11),
        ('ALIGN',         (0,0),  (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS',(0,1),  (-1,-2), [colors.white, colors.HexColor('#ECF0F1')]),
        ('BACKGROUND',    (0,-1), (-1,-1), colors.HexColor('#27AE60')),
        ('TEXTCOLOR',     (0,-1), (-1,-1), colors.white),
        ('FONTNAME',      (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('GRID',          (0,0),  (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT',     (0,0),  (-1,-1), 25),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # График
    chart_buffer.seek(0)
    story.append(RLImage(chart_buffer, width=500, height=210))
    story.append(Spacer(1, 20))

    # Детализация
    story.append(Paragraph("Детализация трат:", section_style))
    detail_data = [['#', 'Дата', 'Описание', 'Категория', 'Сумма (руб.)']]
    for i, row in enumerate(rows, 1):
        detail_data.append([str(i), row[4][:10], row[2][:30], row[3], f"{row[1]:.2f}"])

    dt = Table(detail_data, colWidths=[30, 80, 180, 100, 80])
    dt.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),  (-1,0),  colors.HexColor('#34495E')),
        ('TEXTCOLOR',     (0,0),  (-1,0),  colors.white),
        ('FONTNAME',      (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),  (-1,-1), 9),
        ('ALIGN',         (0,0),  (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS',(0,1),  (-1,-1), [colors.white, colors.HexColor('#ECF0F1')]),
        ('GRID',          (0,0),  (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT',     (0,0),  (-1,-1), 20),
    ]))
    story.append(dt)

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# ===================== ОБРАБОТЧИКИ =====================

# --- /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
                 "Привет! Я твой финансовый помощник!\n\n"
                 "Напиши сумму и описание:\n"
                 "`500 обед`\n"
                 "`1200 такси`\n\n"
                 "Используй кнопки ниже 👇",
                 reply_markup=create_main_keyboard(),
                 parse_mode='Markdown')

# --- 📊 Статистика ---
@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats_handler(message):
    bot.send_message(message.chat.id,
                     "📊 Выбери период для статистики:",
                     reply_markup=create_period_keyboard('stats'))

# --- 📜 История трат ---
@bot.message_handler(func=lambda m: m.text == "📜 История трат")
def history_handler(message):
    bot.send_message(message.chat.id,
                     "📜 Выбери период для истории:",
                     reply_markup=create_period_keyboard('history'))

# --- ❌ Удалить трату ---
@bot.message_handler(func=lambda m: m.text == "❌ Удалить трату")
def delete_handler(message):
    bot.send_message(message.chat.id,
                     "❌ Выбери период чтобы найти трату для удаления:",
                     reply_markup=create_period_keyboard('delete'))

# --- 📄 PDF отчёт ---
@bot.message_handler(func=lambda m: m.text == "📄 PDF отчёт")
def pdf_handler(message):
    bot.send_message(message.chat.id,
                     "📄 Выбери период для PDF отчёта:",
                     reply_markup=create_period_keyboard('pdf'))

# --- 🗑️ Сбросить данные ---
@bot.message_handler(func=lambda m: m.text == "🗑️ Сбросить данные")
def clear_handler(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Да, удалить всё", callback_data="confirm_clear"),
        InlineKeyboardButton("❌ Отмена",           callback_data="cancel_clear")
    )
    bot.send_message(message.chat.id,
                     "⚠️ Ты уверен? Это удалит ВСЕ записи!",
                     reply_markup=markup)

# --- ❓ Помощь ---
@bot.message_handler(func=lambda m: m.text == "❓ Помощь")
def help_handler(message):
    bot.send_message(message.chat.id,
                     "📖 *Как пользоваться ботом:*\n\n"
                     "💬 *Добавить трату:*\n"
                     "Напиши сумму и описание: `500 обед`\n\n"
                     "📊 *Статистика* — итог по категориям за период\n\n"
                     "📜 *История трат* — список всех трат за период\n\n"
                     "❌ *Удалить трату* — выборочное удаление\n\n"
                     "📄 *PDF отчёт* — красивый отчёт с графиками\n\n"
                     "🗑️ *Сбросить данные* — удалить всё\n\n"
                     "📌 *Категории определяются автоматически:*\n"
                     "Еда, Транспорт, Дом, Развлечения, Здоровье, Связь",
                     parse_mode='Markdown',
                     reply_markup=create_main_keyboard())

# ===================== CALLBACK =====================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    # --- Статистика ---
    if data.startswith('stats_'):
        period = data.replace('stats_', '')
        rows, label = get_expenses_by_period(period)

        if not rows:
            bot.edit_message_text("За этот период трат нет!",
                                  call.message.chat.id, call.message.message_id)
            return

        categories = {}
        total = 0
        for row in rows:
            categories[row[3]] = categories.get(row[3], 0) + row[1]
            total += row[1]

        text = f"📊 *{label}*\n\n💰 *Итого: {total:.2f} ₽*\n\n*По категориям:*\n"
        max_amount = max(categories.values())
        for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            bar = '█' * int((amount / max_amount) * 10) + '░' * (10 - int((amount / max_amount) * 10))
            text += f"{bar} {cat}: {amount:.2f} ₽\n"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

    # --- История ---
    elif data.startswith('history_'):
        period = data.replace('history_', '')
        rows, label = get_expenses_by_period(period)

        if not rows:
            bot.edit_message_text("За этот период трат нет!",
                                  call.message.chat.id, call.message.message_id)
            return

        text = f"📜 *История: {label}*\n\n"
        for row in rows[:15]:
            text += f"🔹 `#{row[0]}` {row[4][:10]} — {row[2]} ({row[3]}): *{row[1]:.2f} ₽*\n"

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

    # --- Удалить трату (показываем список) ---
    elif data.startswith('delete_') and not data.startswith('delete_id_'):
        period = data.replace('delete_', '')
        rows, label = get_expenses_by_period(period)

        if not rows:
            bot.edit_message_text("За этот период трат нет!",
                                  call.message.chat.id, call.message.message_id)
            return

        markup = InlineKeyboardMarkup()
        text = f"❌ *Выбери трату для удаления ({label}):*\n\n"

        for row in rows[:10]:
            text += f"`#{row[0]}` {row[4][:10]} — {row[2]}: *{row[1]:.2f} ₽*\n"
            markup.add(InlineKeyboardButton(
                f"❌ #{row[0]} | {row[2]} | {row[1]:.2f} ₽",
                callback_data=f"delete_id_{row[0]}"
            ))

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode='Markdown', reply_markup=markup)

    # --- Удалить конкретную трату ---
    elif data.startswith('delete_id_'):
        expense_id = int(data.replace('delete_id_', ''))

        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('SELECT amount, description, category FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()

        if row:
            cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, f"Трата #{expense_id} удалена!")
            bot.edit_message_text(
                f"✅ *Удалена трата:*\n"
                f"*{row[0]:.2f} ₽* — {row[1]} ({row[2]})\n\n"
                f"Нажми ❌ *Удалить трату* ещё раз чтобы продолжить",
                call.message.chat.id, call.message.message_id, parse_mode='Markdown'
            )
        else:
            conn.close()
            bot.answer_callback_query(call.id, "Трата не найдена!")

    # --- PDF ---
    elif data.startswith('pdf_'):
        period = data.replace('pdf_', '')
        bot.edit_message_text("Генерирую PDF отчёт, подожди...",
                              call.message.chat.id, call.message.message_id)

        pdf_buffer = create_pdf_report(period)
        if pdf_buffer is None:
            bot.send_message(call.message.chat.id, "За этот период трат нет!")
            return

        _, label = get_date_range(period)
        filename = f"report_{period}_{datetime.now().strftime('%d%m%Y')}.pdf"
        bot.send_document(call.message.chat.id, (filename, pdf_buffer),
                          caption=f"📄 PDF отчёт: {label}",
                          reply_markup=create_main_keyboard())

    # --- Подтверждение сброса ---
    elif data == 'confirm_clear':
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses')
        conn.commit()
        conn.close()
        bot.edit_message_text("🗑️ Все данные удалены!",
                              call.message.chat.id, call.message.message_id)

    elif data == 'cancel_clear':
        bot.edit_message_text("❌ Удаление отменено",
                              call.message.chat.id, call.message.message_id)

# --- Добавление трат ---
@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    if message.text in ALL_BUTTONS:
        return

    try:
        parts  = message.text.strip().split()
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
    except:
        bot.reply_to(message,
                     "❌ Ошибка! Пиши: сумма описание\nПример: `500 такси`",
                     reply_markup=create_main_keyboard())

print("Running bot...")
bot.infinity_polling()



