import os
import telebot
import sqlite3
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io

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

# --- Главная клавиатура ---
def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_stats = KeyboardButton("📊 Посмотреть итоги")
    btn_history = KeyboardButton("📜 История трат")
    btn_pdf = KeyboardButton("📄 PDF отчёт")
    btn_clear = KeyboardButton("🗑️ Сбросить данные")
    markup.add(btn_stats, btn_history)
    markup.add(btn_pdf, btn_clear)
    return markup

# --- Клавиатура для выбора периода ---
def create_period_keyboard(action):
    markup = InlineKeyboardMarkup()
    btn_today = InlineKeyboardButton("📅 Сегодня", callback_data=f"{action}_today")
    btn_week = InlineKeyboardButton("📅 Неделя", callback_data=f"{action}_week")
    btn_month = InlineKeyboardButton("📅 Месяц", callback_data=f"{action}_month")
    btn_all = InlineKeyboardButton("📅 Всё время", callback_data=f"{action}_all")
    markup.add(btn_today, btn_week)
    markup.add(btn_month, btn_all)
    return markup

# --- Получить даты для периода ---
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
    cursor.execute('SELECT id, amount, description, category, date FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC', (start, end))
    rows = cursor.fetchall()
    conn.close()
    return rows, label

# --- Создать PDF с графиком ---
def create_pdf_report(period):
    rows, label = get_expenses_by_period(period)

    if not rows:
        return None

    # Собираем данные по категориям
    categories = {}
    total = 0
    for row in rows:
        cat = row[3]
        amount = row[1]
        categories[cat] = categories.get(cat, 0) + amount
        total += amount

    # --- Создаём график через matplotlib ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('#f8f9fa')

    # График 1: Круговая диаграмма
    cat_names = list(categories.keys())
    cat_values = list(categories.values())
    colors_list = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']

    ax1.pie(cat_values,
            labels=cat_names,
            autopct='%1.1f%%',
            colors=colors_list[:len(cat_names)],
            startangle=90)
    ax1.set_title(f'Распределение трат\n{label}', fontsize=14, fontweight='bold', pad=20)

    # График 2: Столбчатая диаграмма
    bars = ax2.bar(cat_names, cat_values, color=colors_list[:len(cat_names)], width=0.6)
    ax2.set_title(f'Суммы по категориям\n{label}', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Сумма (₽)', fontsize=12)
    ax2.set_facecolor('#f8f9fa')

    # Подписи на столбцах
    for bar, value in zip(bars, cat_values):
        ax2.text(bar.get_x() + bar.get_width() / 2.,
                 bar.get_height() + max(cat_values) * 0.01,
                 f'{value:.0f}₽',
                 ha='center', va='bottom', fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Сохраняем график в буфер
    chart_buffer = io.BytesIO()
    plt.savefig(chart_buffer, format='png', dpi=150, bbox_inches='tight')
    chart_buffer.seek(0)
    plt.close()

    # --- Создаём PDF ---
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                            rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30)

    story = []
    styles = getSampleStyleSheet()

    # Заголовок
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2C3E50')
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        textColor=colors.HexColor('#7F8C8D')
    )

    story.append(Paragraph("Финансовый отчёт", title_style))
    story.append(Paragraph(f"{label} | Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}", subtitle_style))
    story.append(Spacer(1, 10))

    # Общая сумма
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Normal'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.HexColor('#27AE60'),
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph(f"Общая сумма трат: {total:.2f} руб.", total_style))
    story.append(Spacer(1, 10))

    # Таблица по категориям
    table_data = [['Категория', 'Сумма (руб.)', 'Доля (%)']]
    for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        percent = (amount / total * 100) if total > 0 else 0
        table_data.append([cat, f"{amount:.2f}", f"{percent:.1f}%"])

    # Итоговая строка
    table_data.append(['ИТОГО', f"{total:.2f}", "100%"])

    table = Table(table_data, colWidths=[200, 150, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#ECF0F1')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#27AE60')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT', (0, 0), (-1, -1), 25),
    ]))

    story.append(table)
    story.append(Spacer(1, 20))

    # Вставляем график
    from reportlab.platypus import Image as RLImage
    chart_buffer.seek(0)
    img = RLImage(chart_buffer, width=500, height=210)
    story.append(img)
    story.append(Spacer(1, 20))

    # Таблица всех трат
    story.append(Paragraph("Детализация трат:", ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=10
    )))

    detail_data = [['#', 'Дата', 'Описание', 'Категория', 'Сумма (руб.)']]
    for i, row in enumerate(rows, 1):
        detail_data.append([
            str(i),
            row[4][:10],
            row[2][:30],
            row[3],
            f"{row[1]:.2f}"
        ])

    detail_table = Table(detail_data, colWidths=[30, 80, 180, 100, 80])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWHEIGHT', (0, 0), (-1, -1), 20),
    ]))

    story.append(detail_table)

    # Строим PDF
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- Команда /start ---
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

# --- Кнопка "Статистика" ---
@bot.message_handler(func=lambda message: message.text == "📊 Посмотреть итоги")
def show_stats_button(message):
    bot.send_message(message.chat.id,
                     "Выбери период:",
                     reply_markup=create_period_keyboard('stats'))

# --- Кнопка "История" ---
@bot.message_handler(func=lambda message: message.text == "📜 История трат")
def show_history_button(message):
    bot.send_message(message.chat.id,
                     "Выбери период:",
                     reply_markup=create_period_keyboard('history'))

# --- Кнопка "PDF отчёт" ---
@bot.message_handler(func=lambda message: message.text == "📄 PDF отчёт")
def show_pdf_button(message):
    bot.send_message(message.chat.id,
                     "Выбери период для PDF отчёта:",
                     reply_markup=create_period_keyboard('pdf'))

# --- Кнопка "Сбросить данные" ---
@bot.message_handler(func=lambda message: message.text == "🗑️ Сбросить данные")
def clear_all_button(message):
    markup = InlineKeyboardMarkup()
    btn_yes = InlineKeyboardButton("✅ Да, удалить всё", callback_data="confirm_clear")
    btn_no = InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear")
    markup.add(btn_yes, btn_no)
    bot.send_message(message.chat.id,
                     "⚠️ Ты уверен? Это удалит ВСЕ записи!",
                     reply_markup=markup)

# --- Обработка callback кнопок ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    # --- Статистика по периоду ---
    if data.startswith('stats_'):
        period = data.replace('stats_', '')
        rows, label = get_expenses_by_period(period)

        if not rows:
            bot.edit_message_text("За этот период трат нет!",
                                  call.message.chat.id,
                                  call.message.message_id)
            return

        categories = {}
        total = 0
        for row in rows:
            cat = row[3]
            amount = row[1]
            categories[cat] = categories.get(cat, 0) + amount
            total += amount

        text = f"📊 **{label}**\n\n"
        text += f"💰 **Итого: {total:.2f} ₽**\n\n"
        text += "**По категориям:**\n"

        categories_sorted = sorted(categories.items(), key=lambda x: x[1], reverse=True)
        max_amount = max(categories.values())

        for cat, amount in categories_sorted:
            bar_length = int((amount / max_amount) * 10)
            bar = '█' * bar_length + '░' * (10 - bar_length)
            text += f"{bar} {cat}: {amount:.2f} ₽\n"

        bot.edit_message_text(text,
                              call.message.chat.id,
                              call.message.message_id,
                              parse_mode='Markdown')

    # --- История по периоду ---
    elif data.startswith('history_'):
        period = data.replace('history_', '')
        rows, label = get_expenses_by_period(period)

        if not rows:
            bot.edit_message_text("За этот период трат нет!",
                                  call.message.chat.id,
                                  call.message.message_id)
            return

        # Показываем по 5 записей с кнопками удаления
        markup = InlineKeyboardMarkup()
        text = f"📜 **История: {label}**\n\n"

        for row in rows[:10]:
            expense_id = row[0]
            amount = row[1]
            description = row[2]
            category = row[3]
            date = row[4][:10]
            text += f"🔹 `#{expense_id}` {date} — {description} ({category}): **{amount:.2f} ₽**\n"

            btn_delete = InlineKeyboardButton(
                f"❌ Удалить #{expense_id}",
                callback_data=f"delete_{expense_id}"
            )
            markup.add(btn_delete)

        bot.edit_message_text(text,
                              call.message.chat.id,
                              call.message.message_id,
                              parse_mode='Markdown',
                              reply_markup=markup)

    # --- Удаление конкретной траты ---
    elif data.startswith('delete_'):
        expense_id = int(data.replace('delete_', ''))

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
                f"✅ Удалена трата:\n"
                f"**{row[0]:.2f} ₽** — {row[1]} ({row[2]})\n\n"
                f"Нажми 📜 История трат чтобы посмотреть остальные",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            conn.close()
            bot.answer_callback_query(call.id, "Трата не найдена!")

    # --- PDF по периоду ---
    elif data.startswith('pdf_'):
        period = data.replace('pdf_', '')
        bot.edit_message_text("⏳ Генерирую PDF отчёт, подожди...",
                              call.message.chat.id,
                              call.message.message_id)

        pdf_buffer = create_pdf_report(period)

        if pdf_buffer is None:
            bot.send_message(call.message.chat.id, "За этот период трат нет!")
            return

        _, label = get_date_range(period)
        filename = f"report_{period}_{datetime.now().strftime('%d%m%Y')}.pdf"

        bot.send_document(
            call.message.chat.id,
            (filename, pdf_buffer),
            caption=f"📄 PDF отчёт: {label}"
        )

    # --- Подтверждение удаления всех данных ---
    elif data == 'confirm_clear':
        conn = sqlite3.connect('expenses.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses')
        conn.commit()
        conn.close()
        bot.edit_message_text("🗑️ Все данные удалены!",
                              call.message.chat.id,
                              call.message.message_id)

    elif data == 'cancel_clear':
        bot.edit_message_text("❌ Удаление отменено",
                              call.message.chat.id,
                              call.message.message_id)

# --- Обработка трат ---
@bot.message_handler(func=lambda message: True)
def handle_expense(message):
    if message.text in ["📊 Посмотреть итоги", "📜 История трат", "📄 PDF отчёт", "🗑️ Сбросить данные"]:
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
        bot.reply_to(message,
                     "❌ Ошибка! Пиши: сумма описание\nПример: `500 такси`",
                     reply_markup=create_main_keyboard())

print("Running bot...")
bot.infinity_polling()
