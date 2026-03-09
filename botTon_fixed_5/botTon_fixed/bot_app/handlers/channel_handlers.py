from aiogram import Router, F, Bot
from aiogram.types import Message
import logging

from bot_app.database import get_setting, set_setting
from bot_app.config import ADMINS, SALE_ADMINS

router = Router()

DEFAULT_CHANNEL_REPLY_TEXT = """🐶 Хай, полезная информация для подписчиков Крипто Вилла 🔽

<blockquote>Пост об навигации в канале:
https://t.me/CryptoAndVilla/3658</blockquote>

<blockquote>Наш чат: https://t.me/cryptovillachat 💬</blockquote>

<blockquote>Правила чата — https://t.me/cryptovillachat/431190 💬</blockquote>

Полезные ссылки:
<blockquote>🔏 <a href="https://t.me/portals/market?startapp=0fkhla">Portals</a> 💬
☁️ <a href="https://t.me/mrkt/app?startapp=8132138841">MRKT</a>
🔏 <a href="https://t.me/tonnel_network_bot/gifts?startapp=ref_8132138841">Tonnel</a></blockquote>

<blockquote>➖ ➖ ➖ ➖ ➖ ➖ ➖ ➖
<a href="https://t.me/cryptovillachat">Чат</a> 🐸 ❕ 🟣 <a href="http://t.me/cryptoVillaVpn_bot">Купить VPN</a> 🧙‍♂️ 🟣 <a href="http://t.me/VillaTon_bot">Наш бот по продаже TON и прочего..</a></blockquote>

<blockquote>🪙 <i>Владелец канала:</i> @cryptotechnologia 💬
⚠️ <i>Менеджер:</i> @utkax
🔔 <i>Данные по прайсу рекламы:</i> https://t.me/cryptovillainfo</blockquote>"""


# Ловит сообщения в группе/супергруппе, которые являются автофорвардом из канала
@router.message(F.chat.type.in_({"supergroup", "group"}), F.is_automatic_forward == True)
async def auto_forward_channel_post(message: Message):
    logging.warning(
        f"[CHANNEL] Автофорвард из канала: chat_id={message.chat.id} "
        f"chat_title={getattr(message.chat, 'title', '-')} "
        f"message_id={message.message_id} "
        f"forward_from_chat={message.forward_from_chat}"
    )
    
    template = await get_setting("channel_reply_template", DEFAULT_CHANNEL_REPLY_TEXT)
    
    try:
        await message.reply(
            text=template,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        logging.info(f"[CHANNEL] Шаблон успешно отправлен в чат {message.chat.id}")
    except Exception as e:
        import traceback
        logging.error(f"[CHANNEL] Ошибка при отправке шаблона: {e}\n{traceback.format_exc()}")


from aiogram.filters import Command

# ... (rest of imports and DEFAULT_CHANNEL_REPLY_TEXT)

# Хендлер для обновления шаблона админом через команду /shablon
@router.message(Command("shablon"), F.chat.type == "private")
async def update_template_command(message: Message):
    # Check if user is in ADMINS or SALE_ADMINS
    allowed_ids = {int(a) for a in ADMINS} | {int(a) for a in SALE_ADMINS}
    if message.from_user.id not in allowed_ids:
        return
    # Извлекаем текст после команды /shablon
    # Используем html_text чтобы сохранить разметку и премиум эмодзи
    full_html = message.html_text
    
    # Ищем, где заканчивается команда. Мы учитываем возможный username бота в команде /shablon@bot
    import re
    command_match = re.search(r"^/shablon(@\w+)?\s*", full_html, re.IGNORECASE)
    
    if not command_match or len(full_html) <= command_match.end():
        current = await get_setting("channel_reply_template", DEFAULT_CHANNEL_REPLY_TEXT)
        await message.reply(
            f"ℹ️ <b>Текущий шаблон:</b>\n\n{current}\n\n"
            f" Чтобы обновить, напиши: <code>/shablon [твой новый текст]</code>\n\n"
            f"<i>Поддерживается HTML разметка и премиум эмодзи.</i>",
            parse_mode="HTML"
        )
        return

    new_template = full_html[command_match.end():]

    await set_setting("channel_reply_template", new_template)
    
    # Отправляем подтверждение и ПРЕДПРОСМОТР
    await message.answer("✅ <b>Шаблон обновлен!</b>\n\nВот так он будет выглядеть под постом:", parse_mode="HTML")
    await message.answer(new_template, parse_mode="HTML", disable_web_page_preview=True)


# Шаблон обновляется только через личку бота (/shablon в канале не ловится этим хендлером)
