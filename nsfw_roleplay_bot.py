import os
import logging
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
        "/reset — сбросить историю\n"
        "/wish — фривольное приветствие и пожелание дня\n"
        "/goodday — нейтральное фривольное приветствие и пожелание дня\n"
        "/joke — пошлый анекдот",
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
    conversations[user_id] = [{"role": "user", "content": scene_text}]

    await query.edit_message_text("Генерирую сцену...")

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
        await query.edit_message_text(ai_reply)

    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await query.edit_message_text(f"Ошибка: {str(e)[:200]}")


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


async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает кнопки выбора режима анекдота"""
    keyboard = [
        [InlineKeyboardButton("AI-анекдот", callback_data="joke_ai")],
        [InlineKeyboardButton("С сайта (API)", callback_data="joke_api")],
        [InlineKeyboardButton("Смешанный", callback_data="joke_mixed")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери режим анекдота:", reply_markup=reply_markup)


async def joke_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    mode = query.data

    if mode == "joke_ai":
        await generate_ai_joke(query)
    elif mode == "joke_api":
        await get_joke_from_site(query)
    elif mode == "joke_mixed":
        # Сначала пробуем сайт, если не получилось — AI
        success = await get_joke_from_site(query, silent=True)
        if not success:
            await generate_ai_joke(query)


async def generate_ai_joke(query):
    prompt = (
        "Придумай очень смешной и оригинальный пошлый анекдот на русском языке. "
        "Тема должна быть разнообразной. Обязательно с подтекстом про связь между мужчинами или упоминанием мужских гениталий. "
        "Анекдот должен быть остроумным, с неожиданной концовкой. 5–10 предложений."
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "Ты мастер разнообразных пошлых анекдотов на русском."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 1.05,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            joke_text = data["choices"][0]["message"]["content"]

        await query.edit_message_text(joke_text)
        return True

    except Exception as e:
        logger.error(f"Ошибка AI-анекдота: {e}")
        await query.edit_message_text(f"Ошибка AI: {str(e)[:200]}")
        return False


async def get_joke_from_site(query, silent=False):
    """Пытается взять анекдот с anekdotov.net или anekdot.ru"""
    import re
    sites = [
        "http://anekdotov.net/intim/chlen/",
        "https://www.anekdot.ru/random/anekdot/",
    ]

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for url in sites:
                try:
                    response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    response.raise_for_status()
                    html = response.text

                    # Простой поиск текста анекдота
                    # Для anekdotov.net
                    matches = re.findall(r'<div class="text">(.*?)</div>', html, re.DOTALL)
                    if not matches:
                        # Для anekdot.ru
                        matches = re.findall(r'<div class="text">(.*?)</div>', html, re.DOTALL)

                    if matches:
                        joke = matches[0]
                        # Очистка от HTML-тегов
                        joke = re.sub(r'<[^>]+>', '', joke)
                        joke = joke.strip()
                        if len(joke) > 50:
                            if not silent:
                                await query.edit_message_text(joke[:3500])
                            return True
                except Exception:
                    continue

        if not silent:
            await query.edit_message_text("Не удалось получить анекдот с сайтов.")
        return False

    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        if not silent:
            await query.edit_message_text("Ошибка при получении анекдота с сайта.")
        return False


async def goodday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует нейтральное фривольное приветствие и пожелание хорошего дня"""
    prompt = (
        "Напиши короткое, лёгкое, нейтрально-фривольное приветствие для мужчины на русском языке. "
        "Обязательно используй слова «приятель» или «дружище». "
        "Не упоминай внешность, как человек выглядит, или что-то, что требует видеть его. "
        "Затем пожелай хорошего дня в том же тоне — игриво, с лёгкой улыбкой и намёком, но без явной пошлости. "
        "Стиль: дружелюбный, слегка кокетливый, подходящий для переписки. 3–5 предложений."
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "Ты пишешь короткие, лёгкие, нейтрально-фривольные приветствия и пожелания дня для переписки. Используй слова «приятель» и «дружище». Не упоминай внешность человека. Тон — дружелюбный, слегка кокетливый."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.85,
                    "max_tokens": 250,
                },
            )
            response.raise_for_status()
            data = response.json()
            wish_text = data["choices"][0]["message"]["content"]

        await update.message.reply_text(wish_text)

    except Exception as e:
        logger.error(f"Ошибка генерации нейтрального пожелания: {e}")
        await update.message.reply_text(f"Ошибка goodday: {str(e)[:300]}")


async def wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует фривольное приветствие и пожелание хорошего дня"""
    user_id = update.effective_user.id

    prompt = (
        "Напиши короткое, фривольное и игривое приветствие для гей-мужчины на русском языке. "
        "Обязательно используй слова «приятель» или «дружище». "
        "Затем пожелай хорошего дня в том же тоне — немного пошло, с лёгким намёком. "
        "Стиль: дружелюбный, сексуальный, с улыбкой. 4–6 предложений."
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "Ты пишешь короткие, фривольные, игривые приветствия и пожелания дня для взрослых мужчин. Тон — лёгкий, сексуальный, с улыбкой."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.9,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()
            wish_text = data["choices"][0]["message"]["content"]

        await update.message.reply_text(wish_text)

    except Exception as e:
        logger.error(f"Ошибка генерации пожелания: {e}")
        await update.message.reply_text(f"Ошибка wish: {str(e)[:300]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    if not message.text:
        await message.reply_text("Пришли текстовое сообщение.")
        return

    conversations[user_id].append({"role": "user", "content": message.text})

    if len(conversations[user_id]) > 10:
        conversations[user_id] = conversations[user_id][-10:]

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
    app.add_handler(CommandHandler("wish", wish))
    app.add_handler(CommandHandler("goodday", goodday))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CallbackQueryHandler(joke_callback, pattern="^joke_"))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
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
