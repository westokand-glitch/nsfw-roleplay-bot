import os
import logging
import base64
from collections import defaultdict
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import httpx

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER")

AI_API_KEY = os.getenv("AI_API_KEY", "ВСТАВЬ_СЮДА_КЛЮЧ_ОТ_GROQ")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.x.ai/v1")
AI_MODEL = os.getenv("AI_MODEL", "grok-3")

# Время утренней рассылки (часы, минуты) по UTC. 6:00 UTC = 9:00 МСК
MORNING_HOUR_UTC = 6
MORNING_MINUTE = 0

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
morning_subscribers = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []

    keyboard = [
        [InlineKeyboardButton("Раздевалка", callback_data="scene_locker"),
         InlineKeyboardButton("Баня", callback_data="scene_sauna")],
        [InlineKeyboardButton("Стройка", callback_data="scene_construction"),
         InlineKeyboardButton("Пляж", callback_data="scene_beach")],
        [InlineKeyboardButton("Отель", callback_data="scene_hotel"),
         InlineKeyboardButton("Машина", callback_data="scene_car")],
        [InlineKeyboardButton("Групповая", callback_data="scene_group")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет. Я твой ролевой NSFW-бот.\n\n"
        "Выбери сценарий или просто напиши свой:\n\n"
        "Команды:\n"
        "/morning — утренняя история (9:00 МСК)\n"
        "/stopmorning — выключить\n"
        "/reset — сбросить историю",
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    scenes = {
        "scene_locker": "Начни сцену в раздевалке после тренировки. Трое потных парней.",
        "scene_sauna": "Начни сцену в бане. Горячий пар, голые мужики.",
        "scene_construction": "Начни сцену на стройке. Рабочие в перерыве.",
        "scene_beach": "Начни сцену на пляже. Двое парней на пустынном участке.",
        "scene_hotel": "Начни сцену в номере отеля.",
        "scene_car": "Начни сцену в машине на парковке.",
        "scene_group": "Начни групповую сцену с 4–5 мужчинами.",
    }

    scene_text = scenes.get(query.data, "Начни новую сцену.")
    conversations[user_id] = [{"role": "user", "content": [{"type": "text", "text": scene_text}]}]

    await query.edit_message_text("Генерирую сцену и изображение...")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[user_id]

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Генерация текста
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
        await query.edit_message_text(ai_reply)

        # Пробуем сгенерировать изображение отдельно
        try:
            async with httpx.AsyncClient(timeout=120.0) as img_client:
                image_prompt = f"Photorealistic gay erotic scene, adult men 18+, {scene_text}. Explicit, detailed, high quality."
                img_response = await img_client.post(
                    f"{AI_BASE_URL}/images/generations",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "grok-imagine-image",
                        "prompt": image_prompt,
                        "n": 1,
                    },
                )
                img_response.raise_for_status()
                img_data = img_response.json()
                image_url = img_data["data"][0]["url"]
                await context.bot.send_photo(chat_id=user_id, photo=image_url)
        except Exception as img_err:
            logger.error(f"Ошибка генерации изображения: {img_err}")

    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await query.edit_message_text("Ошибка при генерации текста. Попробуй ещё раз.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text("История сброшена. Начинаем новую сцену.")


async def morning_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    morning_subscribers.add(user_id)
    await update.message.reply_text("Утренняя история включена. Каждый день в 9:00 по Москве пришлю новую сцену.")


async def morning_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    morning_subscribers.discard(user_id)
    await update.message.reply_text("Утренняя история выключена.")


async def send_morning_story(context: ContextTypes.DEFAULT_TYPE):
    if not morning_subscribers:
        return

    prompt = (
        "Напиши короткую, но подробную гей-эротическую сцену на русском языке. "
        "Начни сразу с описания, без приветствий. В конце предложи 2 варианта продолжения."
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.9,
                    "max_tokens": 700,
                },
            )
            response.raise_for_status()
            data = response.json()
            story = data["choices"][0]["message"]["content"]

        for user_id in list(morning_subscribers):
            try:
                await context.bot.send_message(chat_id=user_id, text=story)
            except Exception as e:
                logger.error(f"Не удалось отправить утреннюю историю {user_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка генерации утренней истории: {e}")


async def get_image_base64(file):
    file_bytes = await file.download_as_bytearray()
    return base64.b64encode(file_bytes).decode("utf-8")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    content = []

    if message.text:
        content.append({"type": "text", "text": message.text})

    if message.photo:
        photo = message.photo[-1]
        file = await photo.get_file()
        b64 = await get_image_base64(file)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
        if not message.caption and not message.text:
            content.insert(0, {"type": "text", "text": "Опиши это изображение подробно в эротическом ключе и продолжи сцену."})

    elif message.animation:
        await message.reply_text("Обрабатываю GIF...")
        file = await message.animation.get_file()
        b64 = await get_image_base64(file)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
        if not message.caption and not message.text:
            content.insert(0, {"type": "text", "text": "Это GIF. Опиши первый кадр подробно в эротическом ключе и продолжи сцену."})

    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file = await message.document.get_file()
        b64 = await get_image_base64(file)
        mime = message.document.mime_type
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"}
        })
        if not message.caption and not message.text:
            content.insert(0, {"type": "text", "text": "Опиши это изображение подробно в эротическом ключе и продолжи сцену."})

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


import asyncio

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
    app.add_handler(CommandHandler("morning", morning_on))
    app.add_handler(CommandHandler("stopmorning", morning_off))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.ANIMATION | filters.Document.IMAGE) & ~filters.COMMAND,
        handle_message
    ))

    # Утренняя рассылка каждый день в 9:00 МСК (6:00 UTC)
    if app.job_queue:
        app.job_queue.run_daily(
            send_morning_story,
            time=time(hour=MORNING_HOUR_UTC, minute=MORNING_MINUTE),
            name="morning_story"
        )

    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    main()
