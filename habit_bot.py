"""
Telegram Habit Tracker Bot
Зависимости: pip install python-telegram-bot==20.7 apscheduler
"""

import json
import os
import logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

# ───────────────────────────────────────────────
# НАСТРОЙКИ — измени под себя
# ───────────────────────────────────────────────
BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"          # Получи у @BotFather
SEND_HOUR = 5                           # 08:00 по Москве (UTC+3)
SEND_MINUTE = 0
REMINDER_HOUR = 18                      # 21:00 по Москве (UTC+3)
REMINDER_MINUTE = 0

HABITS = [
    "🏃 Зарядка / спорт",
    "📚 Чтение 20 минут",
    "💧 Выпить 2л воды",
    "🧘 Медитация",
    "🛏 Лечь спать до 23:00",
]
# ───────────────────────────────────────────────

DATA_FILE = "habit_data.json"


# ── Работа с данными ──────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_today() -> str:
    return date.today().isoformat()


def get_user(data: dict, user_id: str) -> dict:
    if user_id not in data:
        data[user_id] = {"history": {}, "chat_id": None, "name": ""}
    return data[user_id]


def get_today_habits(user: dict) -> dict:
    today = get_today()
    if today not in user["history"]:
        user["history"][today] = {h: None for h in HABITS}
    return user["history"][today]


# ── Клавиатура ────────────────────────────────

def build_keyboard(habits_today: dict) -> InlineKeyboardMarkup:
    buttons = []
    for habit, status in habits_today.items():
        if status is True:
            label = f"✅ {habit}"
            cb = f"unmark|{habit}"
        elif status is False:
            label = f"❌ {habit}"
            cb = f"mark|{habit}"
        else:
            label = f"⬜ {habit}"
            cb = f"mark|{habit}"
        buttons.append([InlineKeyboardButton(label, callback_data=cb)])
    buttons.append([InlineKeyboardButton("📊 Статистика за неделю", callback_data="stats")])
    return InlineKeyboardMarkup(buttons)


def build_message(habits_today: dict) -> str:
    done = sum(1 for v in habits_today.values() if v is True)
    total = len(habits_today)
    return (
        f"📋 *Привычки на сегодня* — {get_today()}\n"
        f"Выполнено: {done}/{total}\n\n"
        "Нажми на привычку, чтобы отметить выполнение:"
    )


# ── Команды ───────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = get_user(data, user_id)
    user["chat_id"] = update.effective_chat.id
    user["name"] = update.effective_user.first_name or ""
    save_data(data)
    await update.message.reply_text(
        f"Привет, {user['name']}! 👋\n\n"
        "Я буду присылать тебе список привычек каждое утро.\n\n"
        "Команды:\n"
        "/habits — показать привычки на сегодня\n"
        "/stats — статистика за 7 дней\n"
        "/help — помощь"
    )


async def cmd_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = get_user(data, user_id)
    user["chat_id"] = update.effective_chat.id
    today = get_today_habits(user)
    save_data(data)
    await update.message.reply_text(
        build_message(today),
        reply_markup=build_keyboard(today),
        parse_mode="Markdown"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    user = get_user(data, user_id)
    await update.message.reply_text(
        build_stats_text(user),
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Habit Bot — помощь*\n\n"
        "/habits — список привычек на сегодня\n"
        "/stats — статистика за 7 дней\n\n"
        "Каждое утро я пришлю список автоматически.\n"
        "Вечером напомню, если не всё отмечено.",
        parse_mode="Markdown"
    )


# ── Обработка кнопок ──────────────────────────

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = load_data()
    user = get_user(data, user_id)
    today = get_today_habits(user)

    if query.data == "stats":
        await query.message.reply_text(build_stats_text(user), parse_mode="Markdown")
        return

    action, habit = query.data.split("|", 1)
    if habit in today:
        today[habit] = True if action == "mark" else None

    save_data(data)
    try:
        await query.edit_message_text(
            build_message(today),
            reply_markup=build_keyboard(today),
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ── Статистика ────────────────────────────────

def build_stats_text(user: dict) -> str:
    history = user.get("history", {})
    sorted_days = sorted(history.keys())[-7:]

    if not sorted_days:
        return "📊 Пока нет данных для статистики."

    lines = ["📊 *Статистика за последние 7 дней:*\n"]
    for day in sorted_days:
        habits = history[day]
        done = sum(1 for v in habits.values() if v is True)
        total = len(habits)
        bar = "🟩" * done + "⬜" * (total - done)
        lines.append(f"`{day}` {bar} {done}/{total}")

    # Общий процент
    all_done = sum(
        1 for d in sorted_days
        for v in history[d].values() if v is True
    )
    all_total = sum(len(history[d]) for d in sorted_days)
    pct = int(all_done / all_total * 100) if all_total else 0
    lines.append(f"\n🏆 Общий результат: *{pct}%*")
    return "\n".join(lines)


# ── Планировщик ───────────────────────────────

async def send_daily(app: Application):
    """Утренняя рассылка всем пользователям."""
    data = load_data()
    for user_id, user in data.items():
        chat_id = user.get("chat_id")
        if not chat_id:
            continue
        today = get_today_habits(user)
        save_data(data)
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=build_message(today),
                reply_markup=build_keyboard(today),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить {user_id}: {e}")


async def send_reminder(app: Application):
    """Вечернее напоминание, если есть невыполненные привычки."""
    data = load_data()
    for user_id, user in data.items():
        chat_id = user.get("chat_id")
        if not chat_id:
            continue
        today = get_today_habits(user)
        undone = [h for h, v in today.items() if v is not True]
        if not undone:
            continue
        text = (
            "⏰ *Напоминание!*\n\n"
            f"Ещё не отмечено {len(undone)} привычек:\n"
            + "\n".join(f"• {h}" for h in undone)
        )
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=build_keyboard(today),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.warning(f"Напоминание не отправлено {user_id}: {e}")


# ── Запуск ────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("habits", cmd_habits))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_callback))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily, "cron",
        hour=SEND_HOUR, minute=SEND_MINUTE,
        args=[app]
    )
    scheduler.add_job(
        send_reminder, "cron",
        hour=REMINDER_HOUR, minute=REMINDER_MINUTE,
        args=[app]
    )
    scheduler.start()

    print("✅ Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
