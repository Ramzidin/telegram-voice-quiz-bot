import json
import random
import logging
import os
from telegram import Update, Voice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

# ==== CONFIG ====
ADMIN_USER_IDS = [5070028239]
QUESTIONS_FILE = 'questions.json'
# ===============

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
GET_NAME, GET_GROUP, WAIT_VOICE = range(3)
user_data_store = {}

# Load or create questions
def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, 'w') as f:
            json.dump([], f)
    with open(QUESTIONS_FILE, 'r') as f:
        return json.load(f)

def save_questions(q_list):
    with open(QUESTIONS_FILE, 'w') as f:
        json.dump(q_list, f, ensure_ascii=False, indent=2)

# === Student Flow ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Введите своё имя:")
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("📚 Введите номер своей группы:")
    return GET_GROUP

async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group'] = update.message.text
    questions = load_questions()
    if not questions:
        await update.message.reply_text("❌ Пока нет доступных вопросов.")
        return ConversationHandler.END

    question = random.choice(questions)
    context.user_data['question'] = question

    await update.message.reply_text(f"📝 Ваш вопрос:\n\n{question}\n\n🎤 Отправьте голосовое сообщение с ответом.")
    return WAIT_VOICE


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice: Voice = update.message.voice
    if not voice:
        await update.message.reply_text("❗ Пожалуйста, отправьте голосовое сообщение.")
        return WAIT_VOICE

    user_info = context.user_data
    # Use .get() to avoid KeyError if any field is missing
    name = user_info.get('name', 'Неизвестно')
    group = user_info.get('group', 'Неизвестно')
    question = user_info.get('question', 'Неизвестно')

    caption = (
        f"🎓 Ответ от студента:\n"
        f"👤 Имя: {name}\n"
        f"🏫 Группа: {group}\n"
        f"❓ Вопрос: {question}"
    )

    # Forward voice to all admins by user ID
    for admin_id in ADMIN_USER_IDS:
        try:
            await context.bot.send_voice(chat_id=admin_id, voice=voice.file_id, caption=caption)
        except Exception as e:
            logger.error(f"Ошибка отправки голосового сообщения админу {admin_id}: {e}")

    await update.message.reply_text("✅ Ваш ответ отправлен преподавателю. Спасибо!")
    return ConversationHandler.END

# === Admin Commands ===
async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Use user ID for admin check
    if update.message.from_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ У вас нет прав для этой команды.")
        return
    q = ' '.join(context.args)
    if not q:
        await update.message.reply_text("❗ Использование: /addquestion ваш вопрос")
        return
    questions = load_questions()
    questions.append(q)
    save_questions(questions)
    await update.message.reply_text("✅ Вопрос добавлен.")

async def list_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ У вас нет прав для этой команды.")
        return
    questions = load_questions()
    if not questions:
        await update.message.reply_text("📭 Список вопросов пуст.")
        return
    msg = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    await update.message.reply_text(f"📋 Вопросы:\n{msg}")

async def remove_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_USER_IDS:
        await update.message.reply_text("⛔ У вас нет прав для этой команды.")
        return
    try:
        idx = int(context.args[0]) - 1
        questions = load_questions()
        if idx < 0 or idx >= len(questions):
            raise IndexError
        removed = questions.pop(idx)
        save_questions(questions)
        await update.message.reply_text(f"🗑 Удалено: {removed}")
    except (IndexError, ValueError):
        await update.message.reply_text("❗ Использование: /removequestion номер_вопроса")
    except Exception as e:
        logger.error(f"Ошибка при удалении вопроса: {e}")
        await update.message.reply_text("❗ Произошла ошибка при удалении вопроса.")

# === Main ===
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        print("❌ BOT_TOKEN не найден в переменных окружения!")
        return

    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
            WAIT_VOICE: [MessageHandler(filters.VOICE, handle_voice)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("addquestion", add_question))
    app.add_handler(CommandHandler("listquestions", list_questions))
    app.add_handler(CommandHandler("removequestion", remove_question))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
