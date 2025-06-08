import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Импортируем функции из твоего кода
from search_alg import find_recipes

# # --- Логирование ---
# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

# --- Переменная для хранения результатов ---
user_results = {}

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Привет!\n\n"
        "🍽️ Я помогу найти тебе любой рецепт.\n"
        "📝 Просто напиши, что ты хочешь приготовить. Например:\n"
        "👉 <i>«Спагетти с креветками»</i>\n"
        "👉 <i>«Пирог с вишней»</i>\n\n"
        "🔍 Я найду подходящие рецепты и покажу их по одному с кнопками навигации."
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user = update.effective_user
    user_id = update.effective_user.id

    print(f"🔍 Поиск по запросу: {query} от {user.id} - {user.first_name} {user.last_name}, @{user.username}")
    results = find_recipes(query, top_n=5)

    if not results:
        await update.message.reply_text("Ничего не найдено.")
        return

    user_results[user_id] = results
    await send_recipe(update, context, user_id, index=0)

# --- Разбиваем текст на страницы по 4096 символов ---
def paginate_text(text, max_length=4096):
    pages = []
    while len(text) > max_length:
        split_index = text.rfind('\n', 0, max_length)
        if split_index == -1:
            split_index = max_length
        pages.append(text[:split_index])
        text = text[split_index:]
    pages.append(text)
    return pages

# --- Разбиваем инструкции по списку ---
def parse_instructions(text):
    text = re.sub(r'\d+\.\s*', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentences = [s[0].upper() + s[1:] if s else '' for s in sentences]
    numbered = [f"{i+1}. {s}" for i, s in enumerate(sentences)]

    return numbered


# --- Показываем текущий рецепт ---
async def send_recipe(update, context, user_id, index, page=0):
    results = user_results.get(user_id)
    if not results:
        await update.message.reply_text("Результаты утеряны. Попробуйте снова.")
        return

    recipe = results[index]
    total = len(results)

    # Форматируем ингредиенты (с количеством)
    ingredients = recipe['ingredients']
    try:
        cleaned = ingredients.strip().strip("[]").replace("‘", "'").replace("’", "'")
        items = [item.strip().strip("'\"") for item in re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", cleaned)]
        ingredients_str = "\n".join([f"• {item}" for item in items if item])
    except Exception as e:
        ingredients_str = ingredients

    # Форматируем инструкции (текст → шаги)
    instructions = recipe['instructions']
    try:
        steps = parse_instructions(instructions)
        instructions_str = "\n".join(steps)  # выводим красиво
    except Exception as e:
        print("Ошибка парсинга:", e)
        instructions_str = instructions

    # Добавляем заголовок рецепта и ингредиенты
    full_text = (
        f"🍽️ <b>{recipe['name']}</b>\n\n"
        f"🧂 <b>Ингредиенты:</b>\n{ingredients_str}\n\n"
        f"📝 <b>Как приготовить:</b>\n{instructions_str}"
    )

    # Делим на страницы
    pages = paginate_text(full_text)
    current_page = min(page, len(pages) - 1)

    # Кнопки навигации
    keyboard = []
    nav_buttons = []

    if index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"prev_{index}"))
    nav_buttons.append(InlineKeyboardButton(f"{index + 1} из {total}", callback_data="noop"))
    if index < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"next_{index}"))

    keyboard.append(nav_buttons)

    if len(pages) > 1:
        nav_buttons2 = []
        if current_page > 0:
            nav_buttons2.append(InlineKeyboardButton("⬆️", callback_data=f"page_prev_{index}_{current_page}"))
        nav_buttons2.append(InlineKeyboardButton(f"Страница {current_page + 1} из {len(pages)}", callback_data="noop"))
        if current_page < len(pages) - 1:
            nav_buttons2.append(InlineKeyboardButton("⬇️", callback_data=f"page_next_{index}_{current_page}"))
        keyboard.append(nav_buttons2)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=pages[current_page], reply_markup=reply_markup, parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            text=pages[current_page], reply_markup=reply_markup, parse_mode='HTML'
        )

# --- Обработка кнопок ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data.split('_')

    if data[0] == 'page':
        direction, index, page = data[1], int(data[2]), int(data[3])
        new_page = page - 1 if direction == "prev" else page + 1
        await send_recipe(update, context, user_id, index, page=new_page)
    else:
        direction, index = data[0], int(data[1])
        new_index = index - 1 if direction == "prev" else index + 1
        if 0 <= new_index < len(user_results.get(user_id, [])):
            await send_recipe(update, context, user_id, new_index)
            
# --- Основной запуск ---
if __name__ == '__main__':
    application = ApplicationBuilder().token("ИМЯ_ТОКЕНА").build()  # Вставь свой токен

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Бот запущен!")
    application.run_polling()
