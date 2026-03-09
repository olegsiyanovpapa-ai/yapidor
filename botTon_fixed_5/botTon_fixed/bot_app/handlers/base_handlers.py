from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
import asyncio
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_app.states import BuyTON
from bot_app.database import get_user_wallet, save_user_wallet, get_ton_connect_session, get_global_stats, save_user
from bot_app.config import ADMINS
from aiogram.types import BufferedInputFile, FSInputFile
import os
from bot_app.services import get_ton_rate, STARS_RATE
from bot_app.ton_connect_manager import ton_connect_manager
from bot_app import database
from bot_app.keyboards import main_kb, ton_main_kb, stars_main_kb, wallet_kb, back_cancel_kb, privacy_policy_kb
from bot_app.ton_utils import raw_to_user_friendly, get_ton_balance, get_usdt_balance, generate_qr_code_image

router = Router()

_main_menu_photo_id = None

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    global _main_menu_photo_id
    uid = message.from_user.id
    user_name = message.from_user.first_name or "друг"
    await save_user(uid, message.from_user.username)
    await state.clear()

    # Сразу отправляем заглушку пока грузятся данные
    handler_dir = os.path.dirname(os.path.abspath(__file__))
    bot_app_dir = os.path.dirname(handler_dir)
    photo_path = os.path.join(bot_app_dir, "assets", "main_menu.jpg")

    loading_caption = f"⏳ <b>Загрузка данных...</b>"

    sent_msg = None
    if os.path.exists(photo_path):
        try:
            if _main_menu_photo_id:
                sent_msg = await message.answer_photo(
                    photo=_main_menu_photo_id,
                    caption=loading_caption,
                    parse_mode="HTML"
                )
            else:
                sent_msg = await message.answer_photo(
                    photo=FSInputFile(photo_path),
                    caption=loading_caption,
                    parse_mode="HTML"
                )
                if sent_msg.photo:
                    _main_menu_photo_id = sent_msg.photo[-1].file_id
        except Exception as e:
            import logging
            logging.error(f"Error sending main menu photo: {e}")
            sent_msg = await message.answer(text=loading_caption, parse_mode="HTML")
    else:
        sent_msg = await message.answer(text=loading_caption, parse_mode="HTML")

    # Теперь собираем данные
    caption, kb = await get_main_menu_data(uid, user_name)

    # Редактируем сообщение с реальными данными
    try:
        if sent_msg.photo:
            await sent_msg.edit_caption(caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await sent_msg.edit_text(text=caption, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Error editing main menu: {e}")

@router.callback_query(F.data == "menu_ton")
async def menu_ton_handler(callback: CallbackQuery):
    await callback.answer()
    market, buy_price, sell_price, *_ = await get_ton_rate()
    # Edit caption to show TON specifics if needed, or just keep main info
    # For now, we update the keyboard to TON menu
    try:
        await callback.message.edit_reply_markup(reply_markup=ton_main_kb())
    except Exception:
        # If message is too old or content is same
        await callback.message.answer("<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  <b>Меню TON</b>", reply_markup=ton_main_kb(), parse_mode="HTML")

@router.callback_query(F.data == "menu_stars")
async def menu_stars_handler(callback: CallbackQuery):
    await callback.answer()
    # Edit keyboard to Stars menu
    try:
        await callback.message.edit_reply_markup(reply_markup=stars_main_kb())
    except Exception:
        await callback.message.answer("<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars <b>Меню Звезд</b>", reply_markup=stars_main_kb(), parse_mode="HTML")

@router.callback_query(F.data == "back_to_initial")
async def back_to_initial_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    caption, kb = await get_main_menu_data(callback.from_user.id, callback.from_user.first_name or "друг")
    
    try:
        # If it's a photo message, we edit the caption
        if callback.message.photo:
            await callback.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=caption, reply_markup=kb, parse_mode="HTML")
    except Exception:
        # Fallback if we can't edit
        await start_handler(callback.message, state)

@router.callback_query(F.data == "privacy_policy")
async def privacy_policy_handler(callback: CallbackQuery):
    await callback.answer()
    policy_text = (
        "📄 <b>Политика Конфиденциальности</b>\n\n"
        "Вы можете ознакомиться с политикой конфиденциальности по ссылке:\n"
        "https://telegra.ph/Politika-Konfidencialnosti-02-26-58"
    )
    try:
        # If it's a photo message, we edit the caption
        if callback.message.photo:
            await callback.message.edit_caption(caption=policy_text, reply_markup=privacy_policy_kb(), parse_mode="HTML")
        else:
            await callback.message.edit_text(text=policy_text, reply_markup=privacy_policy_kb(), parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Error in privacy_policy_handler: {e}")

async def get_main_menu_data(user_id: int, first_name: str):
    """Helper to generate main menu caption and keyboard with up-to-date stats"""
    (market, buy_price, sell_price, *_), global_stats = await asyncio.gather(
        get_ton_rate(),
        get_global_stats()
    )

    stats_text = (
        f"<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>Статистика сервиса:</b>\n"
        f"<tg-emoji emoji-id=\"5393201411523625558\">🎁</tg-emoji>  Куплено TON: <b>{global_stats['ton_bought']:.2f}</b>\n"
        f"<tg-emoji emoji-id=\"5393201411523625558\">🎁</tg-emoji>  Куплено Stars: <b>{global_stats['stars_bought']}</b>\n"
        f"<tg-emoji emoji-id=\"5393201411523625558\">🎁</tg-emoji>  Куплено Premium: <b>{global_stats['premium_bought']}</b>\n"
        f"<tg-emoji emoji-id=\"5393201411523625558\">🎁</tg-emoji>  Куплено Подарков: <b>{global_stats['gifts_bought']}</b>\n\n"
    )

    caption = (
        f"<tg-emoji emoji-id=\"5472427507842032538\">🎁</tg-emoji>  <b>Привет, {first_name}!</b>\n\n"
        f"<tg-emoji emoji-id=\"5255883984151276991\">🎁</tg-emoji>  Добро пожаловать в <b>Crypto Villa</b>\n"
        f"🆔 Ваш ID: <code>{user_id}</code>\n\n"
        f"{stats_text}"
        f"<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  <b>Курс TON:</b>\n"
        f"   • Рынок: <b>{market} ₽</b>\n"
        f"   • Покупка: <b>{buy_price} ₽</b>\n"
        f"   • Продажа: <b>{sell_price} ₽</b>\n\n"
        f"<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars <b>Курс Звезд:</b>\n"
        f"   • Покупка: <b>{STARS_RATE} ₽</b> за 1 звезду\n\n"
        f"<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  Принимаем: Карты РФ, СБП\n\n"
        f"🆘 Поддержка бота — @UtkaX"
    )
    
    is_admin = user_id in ADMINS
    return caption, main_kb(is_admin=is_admin)

@router.callback_query(F.data == "my_wallet")
async def my_wallet_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        # Check TON Connect session first
        ton_connect_wallet = await ton_connect_manager.get_connected_wallet(callback.from_user.id)
        
        if ton_connect_wallet:
            # Fetch balances
            ton_balance = await get_ton_balance(ton_connect_wallet)
            usdt_balance = await get_usdt_balance(ton_connect_wallet)
            
            friendly_address = raw_to_user_friendly(ton_connect_wallet)
            text = (
                f"💼 <b>Твой кошелёк (TON Connect):</b>\n"
                f"🔗 <b>Подключен через Tonkeeper</b>\n\n"
                f"📥 <b>Raw:</b> <code>{ton_connect_wallet}</code>\n"
                f"✅ <b>Адрес:</b> <code>{friendly_address}</code>\n\n"
                f"💰 <b>Баланс:</b>\n"
                f"• TON: <b>{ton_balance:.4f}</b> TON\n"
                f"• USDT: <b>{usdt_balance:.2f}</b> USDT"
            )
            kb = wallet_kb(ton_connect_wallet, is_ton_connect=True)
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            # Fallback to manual wallet
            wallet = await get_user_wallet(callback.from_user.id)
            if wallet:
                # Fetch balances
                ton_balance = await get_ton_balance(wallet)
                usdt_balance = await get_usdt_balance(wallet)
                
                friendly_address = raw_to_user_friendly(wallet)
                text = (
                    f"💼 <b>Твой кошелёк:</b>\n"
                    f"📥 <b>Raw:</b> <code>{wallet}</code>\n"
                    f"✅ <b>Адрес:</b> <code>{friendly_address}</code>\n\n"
                    f"💰 <b>Баланс:</b>\n"
                    f"• TON: <b>{ton_balance:.4f}</b> TON\n"
                    f"• USDT: <b>{usdt_balance:.2f}</b> USDT\n\n"
                    f"💡 Рекомендуем подключить через Tonkeeper!"
                )
                kb = wallet_kb(wallet, is_ton_connect=False)
                if callback.message.photo:
                    await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
                else:
                    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            else:
                text = (
                    "💼 <b>Кошелёк не подключен</b>\n\n"
                    "Подключите кошелёк через Tonkeeper или введите адрес вручную."
                )
                kb = wallet_kb(None, is_ton_connect=False)
                if callback.message.photo:
                    await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
                else:
                    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Error in my_wallet_handler: {e}")
        await callback.message.answer("❌ Ошибка загрузки кошелька.")

@router.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await start_handler(callback.message, state) # Pass state now

@router.callback_query(F.data == "change_wallet")
async def change_wallet_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "✍️ Введите адрес вашего TON кошелька:",
        reply_markup=back_cancel_kb("my_wallet")
    )
    await state.set_state(BuyTON.waiting_wallet)

@router.message(BuyTON.waiting_wallet)
async def wallet_input_handler(message: Message, state: FSMContext):
    wallet = message.text.strip()
    if len(wallet) < 48 or not (wallet.startswith("EQ") or wallet.startswith("UQ")):
        await message.answer("❌ Некорректный адрес. Должен начинаться на EQ или UQ.")
        return
    
    await save_user_wallet(message.from_user.id, wallet)
    await message.answer(f"✅ Кошелёк сохранён: <code>{wallet}</code>", parse_mode="HTML")
    await state.clear()
    await start_handler(message, state)

@router.callback_query(F.data == "connect_tonkeeper")
async def connect_tonkeeper_handler(callback: CallbackQuery, state: FSMContext):
    """Handle Tonkeeper wallet connection via TON Connect"""
    await callback.answer()
    
    try:
        # Generate connection URL
        connect_url = await ton_connect_manager.generate_connect_url(callback.from_user.id)
        
        # Generate QR code
        qr_image = generate_qr_code_image(connect_url)
        
        # Send QR code
        photo = BufferedInputFile(qr_image.read(), filename="tonkeeper_qr.png")
        await callback.message.answer_photo(
            photo=photo,
            caption=(
                "🔗 <b>Подключение Tonkeeper</b>\n\n"
                "1️⃣ Отсканируйте QR-код в приложении Tonkeeper\n"
                "2️⃣ Или нажмите кнопку ниже на мобильном устройстве\n"
                "3️⃣ Подтвердите подключение в кошельке\n\n"
                "⏱ Ожидание подключения (до 5 минут)..."
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder()
                .button(text="📱 Открыть Tonkeeper", url=connect_url)
                .button(text="Отмена", callback_data="cancel_connect", icon_custom_emoji_id="5210952531676504517")
                .adjust(1)
                .as_markup()
        )
        
        # Run monitoring in a background task so we don't block the current handler
        asyncio.create_task(monitor_connection(callback.from_user.id, callback.message))
        
    except Exception as e:
        import logging
        logging.error(f"[TON-CONNECT] ❌ Error in connect_tonkeeper handler: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Ошибка подключения</b>\n\n"
            f"Попробуйте позже или введите адрес вручную.\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )

async def monitor_connection(user_id: int, message: Message):
    """Background task to monitor connection and notify user"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[TON-CONNECT] 🚀 Background monitor started for user {user_id}")
    try:
        wallet_address = await ton_connect_manager.wait_for_connection(user_id)
        
        if wallet_address:
            logger.info(f"[TON-CONNECT] 🎉 SUCCESS! user={user_id} wallet={wallet_address}")
            friendly_address = raw_to_user_friendly(wallet_address)
            kb = InlineKeyboardBuilder()
            kb.button(text="↩️ В главное меню", callback_data="back_to_main")
            
            await message.answer(
                f"✅ <b>Кошелёк успешно подключен!</b>\n\n"
                f"📥 <b>Raw:</b> <code>{wallet_address}</code>\n"
                f"✅ <b>Удобный адрес:</b> <code>{friendly_address}</code>",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            logger.warning(f"[TON-CONNECT] ❌ Monitor returned None for user {user_id} — timeout or failure")
            await message.answer(
                "❌ <b>Подключение не завершено</b>\n\n"
                "Если вы подтвердили вход в приложении, но бот этого не увидел — попробуйте снова.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardBuilder().button(text="⚙️ Кошелёк", callback_data="my_wallet").as_markup()
            )
    except Exception as e:
        import logging
        logging.error(f"[TON-CONNECT] ❌ CRITICAL ERROR in monitor_connection for user {user_id}: {e}", exc_info=True)

@router.callback_query(F.data == "disconnect_wallet")
async def disconnect_wallet_handler(callback: CallbackQuery):
    """Disconnect TON Connect wallet"""
    await callback.answer()
    
    try:
        await ton_connect_manager.disconnect_wallet(callback.from_user.id)
        # Check for manual wallet to show correct KB
        manual_wallet = await database.get_user_wallet(callback.from_user.id)
        text = (
            "✅ <b>Tonkeeper отключен</b>\n\n"
            "Вы можете подключить его снова или использовать ручной ввод."
        )
        kb = wallet_kb(manual_wallet, is_ton_connect=False)
        
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        import logging
        logging.error(f"Disconnect error: {e}")
        await callback.answer("❌ Ошибка при отключении", show_alert=True)

@router.callback_query(F.data == "delete_wallet")
async def delete_manual_wallet_handler(callback: CallbackQuery):
    """Delete manual TON wallet"""
    await callback.answer()
    from bot_app.database import delete_user_wallet
    await delete_user_wallet(callback.from_user.id)
    
    text = (
        "✅ <b>Адрес кошелька удален</b>\n\n"
        "Вы можете ввести новый адрес или подключить Tonkeeper."
    )
    kb = wallet_kb(None, is_ton_connect=False)
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "cancel_connect")
async def cancel_connect_handler(callback: CallbackQuery):
    """Cancel wallet connection"""
    await callback.answer("Подключение отменено")
    await callback.message.edit_caption(
        caption="❌ Подключение отменено",
        reply_markup=None
    )
