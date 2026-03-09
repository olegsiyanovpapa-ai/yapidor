import asyncio
from pyrogram import Client
from bot_app.config import USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION_NAME
import os

async def main():
    if not USERBOT_API_ID or not USERBOT_API_HASH:
        print("❌ Ошибка: USERBOT_API_ID или USERBOT_API_HASH не установлены в .env или config.py")
        return

    print("🚀 Запуск настройки UserBot...")
    print(f"Используем API_ID: {USERBOT_API_ID}")
    
    # Session file will be created in the current directory
    async with Client(USERBOT_SESSION_NAME, api_id=USERBOT_API_ID, api_hash=USERBOT_API_HASH) as app:
        me = await app.get_me()
        print(f"✅ Успешный вход!")
        print(f"Аккаунт: {me.first_name} (@{me.username if me.username else 'нет юзернейма'})")
        print(f"ID: {me.id}")
        print("\nФайл сессии успешно создан. Теперь бот сможет отправлять подарки от твоего имени.")

if __name__ == "__main__":
    asyncio.run(main())
