import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ================= НАСТРОЙКИ =================
# ВСТАВЬ СЮДА ТОКЕН ОТ @BotFather (обязательно в прямых кавычках)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# ВСТАВЬ СЮДА СВОЙ USER_ID (число, в квадратных скобках)
ADMIN_IDS =""

# Пароль для входа в админку
ADMIN_PASSWORD = "admin123"

COUNTRY_FLAGS = {
    "Россия": "🇷🇺", "Англия": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Испания": "🇪🇸",
    "Италия": "🇮🇹", "Германия": "🇩🇪", "Франция": "🇫🇷"
}

DB_NAME = "bot_database.db"
# =============================================

# ================= БАЗА ДАННЫХ =================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        username TEXT, 
        is_premium BOOLEAN DEFAULT 0,
        premium_until DATE, 
        matches_today INTEGER DEFAULT 0, 
        last_reset DATE
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        country TEXT, 
        name TEXT
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        league_id INTEGER, 
        title TEXT,
        prediction TEXT, 
        analysis TEXT, 
        halves TEXT, 
        injuries_suspensions TEXT, 
        stats TEXT
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        username TEXT,
        text TEXT, 
        answered BOOLEAN DEFAULT 0
    )""")
    
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_NAME)

def get_or_create_user(user_id: int, username: Optional[str]) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, last_reset) VALUES (?, ?, ?)", 
                (user_id, username, today))
    
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row: 
        return {}
    
    user = {
        "user_id": row, "username": row, "is_premium": bool(row),
        "premium_until": row, "matches_today": row, "last_reset": row,
    }
    
    last_reset = datetime.fromisoformat(user["last_reset"]).date() if user["last_reset"] else None
    if last_reset != datetime.now().date():
        conn = get_conn()
        cur = conn.cursor()
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
    return [{"id": r, "country": r, "name": r} for r in rows]

def add_match(league_id: int, title: str, prediction: str, analysis: str, halves: str, injuries: str, stats: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO matches (league_id, title, prediction, analysis, halves, injuries_suspensions, stats)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", (league_id, title, prediction, analysis, halves, injuries, stats))
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
    return [{"id": r, "title": r} for r in rows]

def get_match_data(match_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT title, prediction, analysis, halves, injuries_suspensions, stats
                    FROM matches WHERE id = ?""", (match_id,))
    row = cur.fetchone()
    conn.close()
    if not row: return None
    return {
        "title": row, "prediction": row, "analysis": row,
        "halves": row, "injuries": row, "stats": row,
    }

def send_support_message(user_id: int, username: str, text: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO support_messages (user_id, username, text) VALUES (?, ?, ?)", (user_id, username, text))
    conn.commit()
    conn.close()

def get_unanswered_support_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM support_messages WHERE answered = 0")
    r = cur.fetchone()
    conn.close()
    return r

def get_support_messages() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, username, text, answered FROM support_messages ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r, "user_id": r, "username": r, "text": r, "answered": bool(r)} for r in rows]

def mark_support_answered(msg_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE support_messages SET answered = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

# ================= FSM (Состояния) =================
class AdminState(StatesGroup):
    waiting_for_password = State()
    adding_match_text = State()
    managing_subscriptions = State()

class SupportState(StatesGroup):
    waiting_for_message = State()

# ================= КЛАВИАТУРЫ =================
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Личный кабинет")
    builder.button(text="⚽ Матчи")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def leagues_keyboard(leagues: List[Dict[str, Any]]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for l in leagues:
        flag = COUNTRY_FLAGS.get(l["country"], "")
        builder.button(text=f"{flag} {l['name']}", callback_data=f"league_{l['id']}")
    builder.adjust(1)
    return builder

def matches_keyboard(matches: List[Dict[str, Any]]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for m in matches:
        builder.button(text=m["title"], callback_data=f"match_{m['id']}")
    builder.adjust(1)
    return builder

def match_tabs_keyboard(match_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    tabs = ["prediction", "analysis", "halves", "injuries", "stats"]
    names = ["Прогноз", "Аналитика", "Таймы", "Травмы и дискв.", "Статистика"]
    for t, n in zip(tabs, names):
        builder.button(text=n, callback_data=f"tab_{match_id}_{t}")
    builder.adjust(5)
    return builder

def admin_keyboard(support_count: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Добавить матч", callback_data="admin_add_match_start")
    builder.button(text=f"📩 Поддержка ({support_count})", callback_data="admin_support_list")
    builder.button(text="💳 Подписки", callback_data="admin_subs_menu")
    builder.button(text="🔙 Назад в меню", callback_data="admin_back")
    builder.adjust(1)
    return builder

# ================= БОТ =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Я футбольный бот: прогнозы, аналитика, статистика.\n"
        "Выбирай кнопки ниже:",
        reply_markup=main_keyboard()
    )

@dp.message(F.text == "👤 Личный кабинет")
async def personal_cabinet(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username)
    premium_status = "Премиум" if user["is_premium"] else "Бесплатный"
    premium_until = user["premium_until"] or "—"
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
        await message.answer("Пока нет лиг. Добавьте их через админку (команда /admin).")
        return
    await message.answer("Выбери лигу:", reply_markup=leagues_keyboard(leagues).as_markup())

@dp.callback_query(F.data.startswith("league_"))
async def show_league_matches(callback: types.CallbackQuery):
    league_id = int(callback.data.split("_"))
    matches = get_matches_by_league(league_id)
    if not matches:
        await callback.answer("В этой лиге пока нет матчей.", show_alert=True)
        return
    await callback.message.edit_text(f"Матчи лиги:", reply_markup=matches_keyboard(matches).as_markup())

@dp.callback_query(F.data.startswith("match_"))
async def show_match_tabs(callback: types.CallbackQuery):
    match_id = int(callback.data.split("_"))
    user = get_or_create_user(callback.from_user.id, callback.from_user.username)

    if not user["is_premium"]:
        if user["matches_today"] >= 3:
            await callback.answer("Лимит матчей исчерпан. Купите премиум через поддержку.", show_alert=True)
            return
        increment_matches(user["user_id"])

    data = get_match_data(match_id)
    if not data:
        await callback.answer("Матч не найден", show_alert=True)
        return

    kb = match_tabs_keyboard(match_id).as_markup()
    await callback.message.edit_text(f"Матч: {data['title']}\n\nВыбери вкладку:", reply_markup=kb)

@dp.callback_query(F.data.startswith("tab_"))
async def show_tab_content(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    match_id = int(parts)
    tab = parts

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
    await callback.message.answer(f"📂 {title}\n\n{content}")

# ================= ПОДДЕРЖКА =================
@dp.callback_query(F.data == "support_start")
async def support_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_for_message)
    await callback.message.answer("Напиши сообщение для поддержки — мы передадим администратору:")

@dp.message(SupportState.waiting_for_message)
async def catch_support_message(message: types.Message, state: FSMContext):
    user = get_or_create_user(message.from_user.id, message.from_user.username)
    send_support_message(user["user_id"], user["username"], message.text)
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📩 Новое сообщение в поддержку!\n"
                     f"От: {user['username']} (ID: {user['user_id']})\n"
                     f"Текст: {message.text}"
            )
        except Exception:
            pass
            
    await message.answer("✅ Сообщение отправлено администратору. Скоро ответим!")
    await state.clear()

# ================= АДМИНКА =================
@dp.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("У вас нет доступа к админ-панели.")
        return
    await state.set_state(AdminState.waiting_for_password)
    await message.answer("Введите пароль для входа в админку:")

@dp.message(AdminState.waiting_for_password)
async def admin_check_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        support_count = get_unanswered_support_count()
        await message.answer("✅ Вход выполнен! Выберите действие:", reply_markup=admin_keyboard(support_count).as_markup())
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль. Попробуйте /admin снова.")
        await state.clear()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    support_count = get_unanswered_support_count()
    await callback.message.edit_text("Меню админа:", reply_markup=admin_keyboard(support_count).as_markup())

@dp.callback_query(F.data == "admin_add_match_start")
async def admin_add_match_country(callback: types.CallbackQuery, state: FSMContext):
    leagues = get_leagues()
    if not leagues:
        await callback.answer("Сначала добавьте лиги!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for l in leagues:
        flag = COUNTRY_FLAGS.get(l["country"], "")
        builder.button(text=f"{flag} {l['name']}", callback_data=f"admin_match_league_{l['id']}")
    builder.adjust(1)
    await callback.message.answer("Выберите лигу для матча:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_match_league_"))
async def admin_add_match_text(callback: types.CallbackQuery, state: FSMContext):
    league_id = int(callback.data.split("_"))
    await state.update_data(league_id=league_id)
    await state.set_state(AdminState.adding_match_text)
    await callback.message.answer(
        "Введите данные матча в формате:\n"
        "Название матча\n\n"
        "**Прогноз**\nТекст прогноза\n\n"
        "**Аналитика**\nТекст аналитики\n\n"
        "**Таймы**\nВремя таймов\n\n"
        "**Травмы и дисквалификации**\nСписок травм\n\n"
        "**Общая статистика**\nСтатистика"
    )

@dp.message(AdminState.adding_match_text)
async def admin_save_match(message: types.Message, state: FSMContext):
    data = await state.get_data()
    league_id = data.get("league_id")
    text = message.text
    
    parts = text.split("\n\n")
    title = parts.strip() if parts else "Матч"
    
    prediction = analysis = halves = injuries = stats = ""
    current_section = None
    
    for line in text.splitlines():
        if line.startswith("**Прогноз**"): current_section = "prediction"
        elif line.startswith("**Аналитика**"): current_section = "analysis"
        elif line.startswith("**Таймы**"): current_section = "halves"
        elif line.startswith("**Травмы и дисквалификации**"): current_section = "injuries"
        elif line.startswith("**Общая статистика**"): current_section = "stats"
        else:
            if current_section == "prediction": prediction += line + "\n"
            elif current_section == "analysis": analysis += line + "\n"
            elif current_section == "halves": halves += line + "\n"
            elif current_section == "injuries": injuries += line + "\n"
            elif current_section == "stats": stats += line + "\n"

    add_match(league_id, title, prediction.strip(), analysis.strip(), halves.strip(), injuries.strip(), stats.strip())
    await message.answer("✅ Матч успешно добавлен!")
    await state.clear()
    
    support_count = get_unanswered_support_count()
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 В меню админа", callback_data="admin_back")
    await message.answer("Что дальше?", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_support_list")
async def admin_support_list(callback: types.CallbackQuery):
    msgs = get_support_messages()
    if not msgs:
        await callback.answer("Нет новых сообщений", show_alert=True)
        return
    
    text = "📩 Сообщения в поддержку:\n\n"
    for m in msgs:
        if not m["answered"]:
            text += f"ID: {m['id']} | От: @{m['username']} (ID: {m['user_id']})\n{m['text']}\n\n"
    
    builder = InlineKeyboardBuilder()
    for m in msgs:
        if not m["answered"]:
            builder.button(text=f"Ответить {m['id']}", callback_data=f"admin_reply_{m['id']}_{m['user_id']}")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_reply_"))
async def admin_reply_start(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    msg_id = int(parts)
    user_id = int(parts)
    await state.update_data(reply_to_user_id=user_id, reply_msg_id=msg_id)
    await state.set_state(AdminState.managing_subscriptions)
    await callback.message.answer(f"Напишите ответ пользователю {user_id}:")

@dp.message(AdminState.managing_subscriptions)
async def admin_send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to_user_id")
    msg_id = data.get("reply_msg_id")
    
    try:
        await bot.send_message(chat_id=user_id, text=f"👤 Ответ от администрации:\n{message.text}")
        mark_support_answered(msg_id)
        await message.answer("✅ Ответ отправлен!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение. Ошибка: {e}")
    
    await state.clear()
    support_count = get_unanswered_support_count()
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 В меню админа", callback_data="admin_back")
    await message.answer("Что дальше?", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_subs_menu")
async def admin_subs_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Поиск пользователя", callback_data="admin_search_user")
    builder.button(text="💳 Выдать всем Премиум", callback_data="admin_give_all_premium")
    builder.button(text="🚫 Снять у всех Премиум", callback_data="admin_revoke_all_premium")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    await callback.message.edit_text("Управление подписками:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_give_all_premium")
async def admin_give_all(callback: types.CallbackQuery):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_premium = 1, premium_until = ?", (datetime.now().date().isoformat(),))
    conn.commit()
    conn.close()
    await callback.answer("✅ Всем пользователям выдан премиум!", show_alert=True)

@dp.callback_query(F.data == "admin_revoke_all_premium")
async def admin_revoke_all(callback: types.CallbackQuery):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_premium = 0, premium_until = NULL")
    conn.commit()
    conn.close()
    await callback.answer("✅ У всех пользователей снят премиум!", show_alert=True)

@dp.callback_query(F.data == "admin_search_user")
async def admin_search_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.managing_subscriptions)
    await callback.message.answer("Введите ID или username пользователя для поиска:")

@dp.message(AdminState.managing_subscriptions)
async def admin_search_user(message: types.Message, state: FSMContext):
    query = message.text.strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ? OR username = ?", (query, query))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        await message.answer("Пользователь не найден.")
        return
    
    user = {
        "user_id": row, "username": row, "is_premium": bool(row),
        "premium_until": row
    }
    
    text = (
        f"👤 Найден пользователь:\n"
        f"ID: {user['user_id']}\n"
        f"Username: @{user['username']}\n"
        f"Статус: {'✅ Премиум' if user['is_premium'] else '❌ Бесплатный'}\n"
        f"До: {user['premium_until'] or '—'}"
    )
    
    builder = InlineKeyboardBuilder()
    if user["is_premium"]:
        builder.button(text="🚫 Снять премиум", callback_data=f"admin_revoke_single_{user['user_id']}")
    else:
        builder.button(text="💳 Выдать премиум", callback_data=f"admin_give_single_{user['user_id']}")
    builder.button(text="🔙 Назад", callback_data="admin_subs_menu")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_give_single_"))
async def admin_give_single(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_"))
    set_premium(user_id, True, (datetime.now() + timedelta(days=30)).isoformat())
    await callback.answer("✅ Премиум выдан!", show_alert=True)
    await admin_search_start(callback, None)

@dp.callback_query(F.data.startswith("admin_revoke_single_"))
async def admin_revoke_single(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_"))
    set_premium(user_id, False)
    await callback.answer("✅ Премиум снят!", show_alert=True)
    await admin_search_start(callback, None)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
