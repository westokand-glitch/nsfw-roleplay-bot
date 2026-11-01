import os
import logging
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import httpx

# Загружаем .env до чтения переменных окружения
load_dotenv()

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "grok-3")

SYSTEM_PROMPT_FILE = Path(os.getenv("SYSTEM_PROMPT_FILE", "SYSTEM_PROMPT.txt"))


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()

    env_prompt = os.getenv("SYSTEM_PROMPT", "").strip()
    if env_prompt:
        return env_prompt

    return "Ты — ролевой бот для взрослых. Отвечай на русском языке."


SYSTEM_PROMPT = load_system_prompt()

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "Не задан TELEGRAM_TOKEN. Создай .env и заполни TELEGRAM_TOKEN."
    )

if not AI_API_KEY:
    raise RuntimeError(
        "Не задан AI_API_KEY. Создай .env и заполни AI_API_KEY."
    )

# История диалогов: user_id -> список сообщений
conversations = defaultdict(list)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []

    await update.message.reply_text(
        "Привет. Я твой ролевой бот.\n\n"
        "Опиши сцену, персонажей и стиль — я продолжу.\n"
        "Команда /reset сбрасывает историю."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text("История сброшена. Начинаем новую сцену.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    if not user_text:
        return

    conversations[user_id].append({"role": "user", "content": user_text})

    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversations[user_id],
    ]

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
                    "messages": messages,
                    "temperature": 0.85,
                    "max_tokens": 1500,
                },
            )
            response.raise_for_status()
            data = response.json()
            ai_reply = data["choices"][0]["message"]["content"]

        conversations[user_id].append(
            {"role": "assistant", "content": ai_reply}
        )

        if len(ai_reply) > 4000:
            for i in range(0, len(ai_reply), 4000):
                await update.message.reply_text(ai_reply[i:i + 4000])
        else:
            await update.message.reply_text(ai_reply)

    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP ошибка AI: %s %s",
            e.response.status_code,
            e.response.text,
        )
        await update.message.reply_text(
            "Ошибка API: проверь ключ, модель и баланс аккаунта."
        )
    except Exception as e:
        logger.exception("Ошибка при генерации ответа: %s", e)
        await update.message.reply_text(
            "Произошла ошибка при генерации ответа. Попробуй ещё раз."
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).connect_timeout(30).read_timeout(30).write_timeout(30).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()