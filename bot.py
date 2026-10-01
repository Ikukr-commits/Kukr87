# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8660358537:AAGzxAODIeLfN3N5SmV0uL1cs5eUUhYosn8"
ADMIN_IDS = "1176756945" # Вставь сюда свой ID (можно узнать у бота @userinfobot)
ADMIN_PASSWORD = "admin123"
# ... остальной код настроек ...

# ================= КЛАВИАТУРЫ =================

def main_keyboard(user_id: int = None):
    """
    Обновленная клавиатура. Кнопка переименована, добавлена проверка на админа.
    """
    builder = ReplyKeyboardBuilder()
    
    # 1. ИЗМЕНЕНИЕ: Кнопка теперь называется "Аккаунт"
    builder.button(text="👤 Аккаунт")
    builder.button(text="⚽ Матчи")
    
    # Опционально: Если пользователь админ, показываем кнопку входа в админку прямо в меню
    if user_id and user_id in ADMIN_IDS:
        builder.button(text="🔐 Админ-панель")
        
    builder.adjust(2, 1) # Две кнопки в ряд, админка отдельно
    return builder.as_markup(resize_keyboard=True)
