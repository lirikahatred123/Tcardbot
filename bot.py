import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")

# Используем MemoryStorage для работы со состояниями (FSM)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Описываем состояния для пошагового диалога
class OsintState(StatesGroup):
    waiting_for_username = State()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я OSINT-бот.\n\n"
        "• Напиши `/osint`, чтобы начать поиск и анализ пользователя.\n"
        "• Отправь обычный текст, чтобы проверить никнейм по соцсетям."
    )

# Шаг 1: Пользователь вводит команду /osint
@dp.message(Command("osint"))
async def cmd_osint(message: Message, state: FSMContext):
    # Переводим бота в состояние ожидания юзернейма
    await state.set_state(OsintState.waiting_for_username)
    await message.answer("🔍 Введите юзернейм (или ссылку) пользователя или канала для анализа:")

# Шаг 2: Бот принимает юзернейм и проводит анализ
@dp.message(OsintState.waiting_for_username)
async def process_osint_username(message: Message, state: FSMContext):
    username = message.text.strip().replace("@", "").replace("https://t.me/", "")
    
    # Очищаем состояние
    await state.clear()
    
    if len(username) < 2:
        await message.answer("⚠️ Слишком короткий юзернейм.")
        return

    status_msg = await message.answer(f"⏳ Провожу OSINT-анализ по цели: `{username}`...", parse_mode="Markdown")

    analysis_results = []
    
    # 1. Собираем открытые данные из Telegram (через API бота)
    try:
        chat = await bot.get_chat(username)
        name = chat.full_name or "Не указано"
        bio = chat.bio or chat.description or "Описание отсутствует"
        user_id = chat.id
        chat_type = chat.type
        
        tg_info = (
            f"🟢 **Telegram Профиль найден:**\n"
            f"• **Тип:** {chat_type}\n"
            f"• **ID:** `{user_id}`\n"
            f"• **Имя / Название:** {name}\n"
            f"• **Био / Описание:** _{bio}_\n"
        )
        analysis_results.append(tg_info)
        
        # Попытка найти зацепки (анализ текста Bio на ключевые слова возраста, пола и т.д.)
        bio_lower = bio.lower()
        clues = []
        if any(word in bio_lower for name_kw in ["лет", "yo", "age", "год"] for word in [name_kw]):
            clues.append("Возможно, в описании указан возраст.")
        if any(w in bio_lower for w in ["м", "ж", "male", "female", "парень", "девушка"]):
            clues.append("Возможно, есть намек на гендер/пол.")
            
        if clues:
            analysis_results.append(f"🔍 **Найденные зацепки в описании:**\n" + "\n".join([f"• {c}" for c in clues]))
            
    except Exception:
        analysis_results.append("❌ В Telegram этот юзернейм не найден или скрыт настройками приватности.")

    # 2. Параллельная проверка по соцсетям (из предыдущего функционала)
    platforms = {
        "GitHub": f"https://github.com/{username}",
        "Instagram": f"https://www.instagram.com/{username}",
        "TikTok": f"https://www.tiktok.com/@{username}",
        "Twitter (X)": f"https://twitter.com/{username}",
        "VK": f"https://vk.com/{username}"
    }

    found_socials = []
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        tasks = []
        urls = list(platforms.items())
        for name, url in urls:
            tasks.append(check_url(session, url))
        results = await asyncio.gather(*tasks)
        
        for i, exists in enumerate(results):
            name, url = urls[i]
            if exists:
                found_socials.append(f"• [{name}]({url})")

    if found_socials:
        analysis_results.append("\n🌐 **Найденные соцсети:**\n" + "\n".join(found_socials))

    # Финальный отчет
    final_text = f"🎯 **Результаты OSINT по `{username}`:**\n\n" + "\n\n".join(analysis_results)
    await status_msg.edit_text(final_text, parse_mode="Markdown", disable_web_page_preview=True)

async def check_url(session, url):
    try:
        async with session.get(url, timeout=4, allow_redirects=True) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass
    return False

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())