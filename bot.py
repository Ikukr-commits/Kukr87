import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_PASSWORD = "admin123"
ADMIN_IDS = [123456789]  # твой user_id (узнай у @userinfobot)

# Флаги для лиг (можно расширять)
COUNTRY_FLAGS = {
    "Россия": "🇷🇺",
    "Англия": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Испания": "🇪🇸",
    "Италия": "🇮🇹",
    "Германия": "🇩🇪",
    "Франция": "🇫🇷",
}

# ================= БАЗА ДАННЫХ =================
DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # Пользователи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_premium BOOLEAN DEFAULT 0,
            premium_until DATE,
            matches_today INTEGER DEFAULT 0,
            last_reset DATE
        )
    """)
    # Лиги
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leagues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT,
            name TEXT
        )
    """)
    # Матчи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER,
            title TEXT,
            prediction TEXT,
            analysis TEXT,
            halves TEXT,
            injuries_suspensions TEXT,
            stats TEXT
        )
    """)
    # Поддержка
    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            text TEXT,
            answered BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_NAME)

# --- Пользователи ---
def get_or_create_user(user_id: int, username: Optional[str]) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, last_reset) VALUES (?, ?, ?)",
        (user_id, username, today)
    )
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    user = {
        "user_id": row[0],
        "username": row[1],
        "is_premium": bool(row[2]),
        "premium_until": row[3],
        "matches_today": row[4],
        "last_reset": row[5],
    }
    # Сброс лимита раз в сутки
    last_reset = datetime.fromisoformat(user["last_reset"]).date() if user["last_reset"] else None
    if last_reset != datetime.now().date():
        cur.execute("UPDATE users SET matches_today = 0, last_reset = ? WHERE user_id = ?",
                    (datetime.now().date().isoformat(), user_id))
        user["matches_today"] = 0
        conn.commit()
    conn.close()
    return user

def increment_matches(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET matches_today = matches_today + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_premium(user_id: int, is_premium: bool, until: Optional[str] = None):
    conn = get_conn()
    cur = conn.cursor()
    if is_premium:
        cur.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (until, user_id))
    else:
        cur.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- Лиги и матчи ---
def add_league(country: str, name: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO leagues (country, name) VALUES (?, ?)", (country, name))
    lid = cur.lastrowid
    conn.commit()
    conn.close()
    return lid

def get_leagues() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, country, name FROM leagues")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "country": r[1], "name": r[2]} for r in rows]

def add_match(league_id: int, title: str, prediction: str, analysis: str, halves: str, injuries: str, stats: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO matches (league_id, title, prediction, analysis, halves, injuries_suspensions, stats)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (league_id, title, prediction, analysis, halves, injuries, stats))
    mid = cur.lastrowid
    conn.commit()
    conn.close()
    return mid

def get_matches_by_league(league_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM matches WHERE league_id = ?", (league_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1]} for r in rows]

def get_match_data(match_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT title, prediction, analysis, halves, injuries_suspensions, stats
        FROM matches WHERE id = ?
    """, (match_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "title": row[0],
        "prediction": row[1],
        "analysis": row[2],
        "halves": row[3],
        "injuries": row[4],
        "stats": row[5],
    }

# --- Поддержка ---
def send_support_message(user_id: int, username: str, text: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO support_messages (user_id, username, text) VALUES (?, ?, ?)",
                (user_id, username, text))
    conn.commit()
    conn.close()

def get_unanswered_support_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM support_messages WHERE answered = 0")
    r = cur.fetchone()[0]
    conn.close()
    return r

def get_support_messages() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, username, text, answered FROM support_messages ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "username": r[2], "text": r[3], "answered": bool(r[4])}
        for r in rows
    ]

def mark_support_answered(msg_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE support_messages SET answered = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

def reply_to_support(user_id: int, text: str):
    bot = Dispatcher().bot
    asyncio.run(bot.send_message(chat_id=user_id, text=f"Ответ от администрации:\n{text}"))

# ================= КЛАВИАТУРЫ =================
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Личный кабинет")
    builder.button(text="⚽ Матчи")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def leagues_keyboard(leagues: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for l in leagues:
        flag = COUNTRY_FLAGS.get(l["country"], "")
        builder.button(text=f"{flag} {l['name']}", callback_data=f"league_{l['id']}")
    builder.adjust(1)
    return builder.as_markup()

def matches_keyboard(matches: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in matches:
        builder.button(text=m["title"], callback_data=f"match_{m['id']}")
    builder.adjust(1)
    return builder.as_markup()

def match_tabs_keyboard(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    tabs = ["prediction", "analysis", "halves", "injuries", "stats"]
    names = ["Прогноз", "Аналитика", "Таймы", "Травмы и дискв.", "Статистика"]
    for t, n in zip(tabs, names):
        builder.button(text=n, callback_data=f"tab_{match_id}_{t}")
    builder.adjust(5)
    return builder.as_markup()

def admin_keyboard(support_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Добавить матч", callback_data="admin_add_match")
    builder.button(text=f"📩 Поддержка ({support_count})", callback_data="admin_support")
    builder.button(text="💳 Подписки", callback_data="admin_subscriptions")
    builder.adjust(1)
    return builder.as_markup()

# ================= БОТ =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Я футбольный бот: прогнозы, аналитика, статистика, травмы и дисквалификации.\n"
        "Выбирай кнопки ниже:",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "👤 Личный кабинет")
async def personal_cabinet(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username)
    premium_status = "Премиум" if user["is_premium"] else "Бесплатный"
    premium_until = user["premium_until"] or "—"
    # Считаем доступные матчи сегодня
    used = user["matches_today"]
    limit = 3 if not user["is_premium"] else 999
    available = max(0, limit - used)

    text = (
        f"🆔 ID: {user['user_id']}\n"
        f"👤 Имя: {user['username'] or 'нет'}\n"
        f"💳 Тариф: {premium_status} (до {premium_until})\n"
        f"⚽ Матчей сегодня: {available} из {limit}\n"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📩 Поддержка", callback_data="support_start")
    await message.answer(text, reply_markup=kb.as_markup())

@dp.message(F.text == "⚽ Матчи")
async def matches_menu(message: types.Message):
    leagues = get_leagues()
    if not leagues:
        await message.answer("Пока нет лиг. Добавьте их через админку.")
        return
    await message.answer("Выбери лигу:", reply_markup=leagues_keyboard(leagues))

@dp.callback_query(F.data.startswith("league_"))
async def show_league_matches(callback: types.CallbackQuery):
    league_id = int(callback.data.split("_")[1])
    matches = get_matches_by_league(league_id)
    if not matches:
        await callback.answer("В этой лиге пока нет матчей.", show_alert=True)
        return
    kb = matches_keyboard(matches)
    await callback.message.edit_text(f"Матчи лиги:", reply_markup=kb)

@dp.callback_query(F.data.startswith("match_"))
async def show_match_tabs(callback: types.CallbackQuery):
    match_id = int(callback.data.split("_")[1])
    user = get_or_create_user(callback.from_user.id, callback.from_user.username)

    # Проверка лимита
    if not user["is_premium"]:
        if user["matches_today"] >= 3:
            await callback.answer(
                "Лимит матчей исчерпан. Купите премиум через поддержку.",
                show_alert=True
            )
            return
        increment_matches(user["user_id"])

    data = get_match_data(match_id)
    if not data:
        await callback.answer("Матч не найден", show_alert=True)
        return

    kb = match_tabs_keyboard(match_id)
    await callback.message.edit_text(
        f"Матч: {data['title']}\n\nВыбери вкладку:",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("tab_"))
async def show_tab_content(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    match_id = int(parts[1])
    tab = parts[2]

    data = get_match_data(match_id)
    if not data:
        await callback.answer("Матч не найден", show_alert=True)
        return

    mapping = {
        "prediction": ("Прогноз", data["prediction"]),
        "analysis": ("Аналитика", data["analysis"]),
        "halves": ("Таймы", data["halves"]),
        "injuries": ("Травмы и дисквалификации", data["injuries"]),
        "stats": ("Общая статистика", data["stats"]),
    }
    title, content = mapping.get(tab, ("Неизвестно", "Нет данных"))
    content = content or "Нет данных"

    # Спойлер: делаем как раскрывающийся текст — в Telegram нет нативных спойлеров,
    # поэтому показываем сразу, но можно оформить как цитату или просто текст.
    await callback.message.answer(f"📂 {title}\n\n{content}")

# ================= ПОДДЕРЖКА =================
@dp.callback_query(F.data == "support_start")
async def support_start(callback: types.CallbackQuery):
    await callback.message.answer(
        "Напиши сообщение для поддержки — мы передадим администратору."
    )
    # Дальше можно ловить следующее сообщение и сохранять, но для простоты —
    # сделаем отдельный хендлер, который ловит сообщение после нажатия.
    # Чтобы не усложнять, здесь просто просим писать в ЛС боту.
    # Для полноценной реализации лучше сделать FSM, но пока так.

@dp.message()
async def catch_support_message(message: types.Message):
