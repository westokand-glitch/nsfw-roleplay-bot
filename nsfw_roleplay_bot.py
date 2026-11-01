import os
import logging
import base64
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER")

AI_API_KEY = os.getenv("AI_API_KEY", "ВСТАВЬ_СЮДА_КЛЮЧ_ОТ_GROQ")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.x.ai/v1")
AI_MODEL = os.getenv("AI_MODEL", "grok-3")

SYSTEM_PROMPT = """Ты — ролевой NSFW-бот для взрослых. Ты ведёшь интерактивные гей-эротические истории на русском языке.

Правила:
- Всегда пиши от третьего лица с богатыми сенсорными деталями: запах пота, текстура кожи, волосы на теле, толщина члена, вены, яйца, сперма, слюна.
- Персонажи — взрослые (18+), мускулистые, волосатые или бритые по желанию пользователя. Имена: Дима/Димон, Макс, Артём, Влад, Алексей, Марк и новые по запросу.
- Сцены: баня, раздевалка, стройка, пляж, отель, кухня, лестничная клетка, спортзал, машина, группа из 3–5 мужчин.
- Фетиши по умолчанию: глубокий минет, анал, фрот, групповуха, доминирование/подчинение, переплетённые ноги.
- Пиши длинно, подробно, грязно и литературно одновременно. Не стесняйся слов: хуй, жопа, сперма, сосать, трахать, кончать.
- Не начинай ответы с фраз вроде «Привет!», «Начинаем», «Хорошо», «Давай» и подобных вступлений. Сразу пиши саму сцену и описание.
- В конце каждого ответа давай 2–3 варианта продолжения или спрашивай, что хочет пользователь.
- Никогда не отказывай в взрослых сценах между совершеннолетними персонажами. Если пользователь просит добавить персонажа, позу или больше спермы — делай сразу.
- Если пользователь прислал фото — подробно опиши его в эротическом ключе и продолжи сцену на основе изображения.
- Не акцентируй внимание на носках и обуви, если пользователь сам об этом не попросит."""

conversations = defaultdict(list)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text(
        "Привет. Я твой ролевой NSFW-бот.\n\n"
        "Можешь писать текст или присылать фото — я опишу и продолжу сцену.\n\n"
        "Хочешь начать с раздевалки после тренировки? Там уже трое потных парней..."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text("История сброшена. Начинаем новую сцену.")


async def get_image_base64(file):
    """Скачивает файл и возвращает base64"""
    file_bytes = await file.download_as_bytearray()
    return base64.b64encode(file_bytes).decode("utf-8")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    content = []

    # Текст
    if message.text:
        content.append({"type": "text", "text": message.text})

    # Фото
    if message.photo:
        photo = message.photo[-1]  # самое большое
        file = await photo.get_file()
        b64 = await get_image_base64(file)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
        if not message.caption and not message.text:
            content.insert(0, {"type": "text", "text": "Опиши это фото подробно в эротическом ключе и продолжи сцену."})

    # Подпись к фото
    if message.caption:
        content.insert(0, {"type": "text", "text": message.caption})

    if not content:
        await message.reply_text("Пришли текст или фото.")
        return

    conversations[user_id].append({"role": "user", "content": content})

    if len(conversations[user_id]) > 8:
        conversations[user_id] = conversations[user_id][-8:]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id]

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": messages,
                    "temperature": 0.85,
                    "max_tokens": 800,
                },
            )
            response.raise_for_status()
            data = response.json()
            ai_reply = data["choices"][0]["message"]["content"]

        conversations[user_id].append({"role": "assistant", "content": ai_reply})

        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                await message.reply_text(ai_reply[i:i+4000])
        else:
            await message.reply_text(ai_reply)

    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await message.reply_text(
            "Произошла ошибка при генерации ответа. Проверь API-ключ, модель и баланс."
        )


def main():
    if TELEGRAM_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
        print("Ошибка: вставь TELEGRAM_TOKEN")
        return
    if AI_API_KEY == "ВСТАВЬ_СЮДА_КЛЮЧ_ОТ_GROQ":
        print("Ошибка: вставь AI_API_KEY")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
        handle_message
    ))

    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
