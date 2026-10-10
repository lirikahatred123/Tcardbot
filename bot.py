import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

CONFIG_FILE = "config.json"

# Загрузка и сохранение настроек
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка чтения конфигурации: {e}")
    return {
        "active_chats": [],
        "interval_hours": 3,
        "card_text": "🎴 **Карточка управления**\n\nИспользуйте `.help` для настройки.",
        "is_enabled": True
    }

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения конфигурации: {e}")

config = load_config()
scheduler = AsyncIOScheduler(timezone="UTC")

# Функция отправки рассылки
async def send_broadcast_message():
    if not config["is_enabled"] or not config["active_chats"]:
        return

    for chat_id in list(config["active_chats"]):
        try:
            await bot.send_message(chat_id, config["card_text"], parse_mode="Markdown")
            logging.info(f"Рассылка отправлена в чат {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка отправки в чат {chat_id}: {e}")

# Обновление таймера
def update_schedule_job():
    scheduler.remove_all_jobs()
    hours = config.get("interval_hours", 3)
    scheduler.add_job(send_broadcast_message, "interval", hours=hours)

# --- КОМАНДЫ (все начинаются с точки) ---

@dp.message(F.text.lower() == ".help")
async def cmd_help(message: Message):
    help_text = (
        "🤖 **Меню управления ботом:**\n\n"
        "• `.help` — Показать эту справку\n"
        "• `.sub` — Подписать текущий чат на рассылку\n"
        "• `.unsub` — Отписать текущий чат от рассылки\n"
        "• `.status` — Посмотреть текущие настройки и текст\n"
        "• `.settext <текст>` — Изменить текст сообщения\n"
        "• `.settime <часы>` — Изменить интервал рассылки (в часах)\n"
        "• `.on` / `.off` — Включить / Выключить рассылку\n"
        "• `.post` — Отправить карточку прямо сейчас"
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(F.text.lower() == ".sub")
async def cmd_sub(message: Message):
    cid = message.chat.id
    if cid not in config["active_chats"]:
        config["active_chats"].append(cid)
        save_config(config)
        await message.answer("✅ Чат успешно добавлен в рассылку!")
    else:
        await message.answer("ℹ️ Этот чат уже подписан.")

@dp.message(F.text.lower() == ".unsub")
async def cmd_unsub(message: Message):
    cid = message.chat.id
    if cid in config["active_chats"]:
        config["active_chats"].remove(cid)
        save_config(config)
        await message.answer("❌ Чат удален из рассылки.")
    else:
        await message.answer("ℹ️ Чата не было в списке рассылки.")

@dp.message(F.text.lower() == ".status")
async def cmd_status(message: Message):
    status_str = "🟢 Активна" if config["is_enabled"] else "🔴 Остановлена"
    text = (
        f"📊 **Статус настроек:**\n\n"
        f"• Состояние: {status_str}\n"
        f"• Интервал: каждые **{config['interval_hours']} ч.**\n"
        f"• Активных чатов: {len(config['active_chats'])}\n\n"
        f"📝 **Текущий текст карточки:**\n{config['card_text']}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.startswith(".settext "))
async def cmd_settext(message: Message):
    new_text = message.text[9:].strip()
    if new_text:
        config["card_text"] = new_text
        save_config(config)
        await message.answer("✅ Текст сообщения успешно сохранен!")
    else:
        await message.answer("⚠️ Напишите текст после команды. Пример: `.settext Мой текст`", parse_mode="Markdown")

@dp.message(F.text.startswith(".settime "))
async def cmd_settime(message: Message):
    try:
        hours = int(message.text[9:].strip())
        if hours > 0:
            config["interval_hours"] = hours
            save_config(config)
            update_schedule_job()
            await message.answer(f"✅ Интервал рассылки обновлен: каждые **{hours} ч.**!")
        else:
            await message.answer("⚠️ Число должно быть больше 0.")
    except ValueError:
        await message.answer("⚠️ Укажите число в часах. Пример: `.settime 2`", parse_mode="Markdown")

@dp.message(F.text.lower() == ".on")
async def cmd_on(message: Message):
    config["is_enabled"] = True
    save_config(config)
    await message.answer("🟢 Авторассылка включена.")

@dp.message(F.text.lower() == ".off")
async def cmd_off(message: Message):
    config["is_enabled"] = False
    save_config(config)
    await message.answer("🔴 Авторассылка выключена.")

@dp.message(F.text.lower() == ".post")
async def cmd_post(message: Message):
    await send_broadcast_message()
    await message.answer("🚀 Сообщение отправлено во все чаты!")

@dp.business_connection()
async def on_business_connect(bc: BusinessConnection):
    logging.info(f"Бизнес-аккаунт подключен: {bc.user.id}")

async def main():
    update_schedule_job()
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())