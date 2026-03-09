from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from bot_app.keyboards import (
    gifts_kb, gift_recipient_kb, main_kb, stars_cancel_kb, 
    back_cancel_kb, gift_conf_kb, signature_selection_kb, payment_actions_kb
)
from bot_app.states import BuyGift
from bot_app.database import create_order, update_order_status, get_order_details
from bot_app.services import STARS_RATE, get_ton_rate, notify_admins
from bot import bot
from datetime import datetime, timedelta

router = Router()

# Gift constants
GIFTS = {
    "heart": {
        "id": "5801108895304779062",
        "name": "Сердце Ван Лав",
        "html_name": "<tg-emoji emoji-id=\"5224628072619216265\">🎁</tg-emoji> Сердце Ван Лав",
        "price": 80,
        "description": "Редкий подарок Сердце Ван Лав",
        "emoji_id": "5224628072619216265"
    },
    "bear": {
        "id": "5800655655995968830",
        "name": "Мишка Ван Лав",
        "html_name": "<tg-emoji emoji-id=\"5226661632259691727\">🎁</tg-emoji> Мишка Ван Лав",
        "price": 80,
        "description": "Редкий подарок Мишка Ван Лав",
        "emoji_id": "5226661632259691727"
    },
    "bear_newyear": {
        "id": "5956217000635139069",
        "name": "Новогодний мишка",
        "html_name": "<tg-emoji emoji-id=\"5379850840691476775\">🎁</tg-emoji> Новогодний мишка",
        "price": 80,
        "description": "Новогодний мишка",
        "emoji_id": "5379850840691476775"
    },
    "tree": {
        "id": "5922558454332916696",
        "name": "Новогодняя Елка",
        "html_name": "<tg-emoji emoji-id=\"5345935030143196497\">🎁</tg-emoji> Новогодняя Елка",
        "price": 80,
        "description": "Новогодняя Елка",
        "emoji_id": "5345935030143196497"
    },
    "bear_8march": {
        "id": "5866352046986232958",
        "name": "Мишка 8 Марта",
        "html_name": "<tg-emoji emoji-id=\"5289761157173775507\">🎁</tg-emoji> Мишка 8 Марта",
        "price": 80,
        "description": "Подарок Мишка 8 Марта",
        "emoji_id": "5289761157173775507"
    }
}

@router.callback_query(F.data == "buy_gift")
async def buy_gift_start(callback: CallbackQuery, state: FSMContext):
    """Start gift purchase flow - Select Recipient"""
    await callback.answer()
    
    await callback.message.answer(
        "<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>Купить редкий подарок</b>\n\n"
        "Выберите, кому хотите купить подарок:",
        reply_markup=gift_recipient_kb(),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "gift_self")
async def gift_self_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(recipient_type="self", recipient_username=None)
    # Initialize defaults
    await state.update_data(is_anonymous=False, signature_text=None)
    
    await show_gift_list(callback.message, is_edit=True, state=state)

@router.callback_query(F.data == "gift_other")
async def gift_other_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(recipient_type="gift")
    # Initialize defaults
    await state.update_data(is_anonymous=False, signature_text=None)
    
    text = (
        f"👤 <b>Подарок другому пользователю</b>\n\n"
        f"Введите username получателя (без @):"
    )
    kb = back_cancel_kb("buy_gift")
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(BuyGift.waiting_recipient_username)

@router.message(BuyGift.waiting_recipient_username)
async def gift_recipient_username_handler(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    
    if not username or len(username) < 3:
        await message.answer("❌ Некорректный username. Попробуйте еще раз:")
        return
    
    await state.update_data(recipient_username=username)
    await show_gift_list(message, is_edit=False, state=state)

@router.callback_query(F.data == "toggle_anonymity")
async def toggle_anonymity_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_anon = data.get("is_anonymous", False)
    await state.update_data(is_anonymous=not is_anon)
    # If anonymous is ON, maybe we should clear signature text? 
    # User says "not allowed with anon".
    if not is_anon: # was False, now True
        await state.update_data(signature_text=None)
    await show_gift_config(callback.message, state)

@router.callback_query(F.data == "change_signature")
async def change_signature_handler(callback: CallbackQuery, state: FSMContext):
    text = (
        "✍️ <b>Выберите тип подписи:</b>\n\n"
        "👤 <b>Юзернейм</b> - получатель увидит ваше имя.\n"
        "✏️ <b>Свой текст</b> - введите любое сообщение.\n"
        "❌ <b>Без подписи</b> - сообщение будет пустым."
    )
    kb = signature_selection_kb()
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "sign_username")
async def set_sign_username(callback: CallbackQuery, state: FSMContext):
    username = callback.from_user.username
    sign = f"@{username}" if username else callback.from_user.first_name
    await state.update_data(signature_text=sign)
    await show_gift_config(callback.message, state)

@router.callback_query(F.data == "sign_none")
async def set_sign_none(callback: CallbackQuery, state: FSMContext):
    await state.update_data(signature_text=None)
    await show_gift_config(callback.message, state)

@router.callback_query(F.data == "sign_custom")
async def set_sign_custom(callback: CallbackQuery, state: FSMContext):
    text = (
        "✏️ <b>Введите текст подписи:</b>\n"
        "(Максимум 50 символов)"
    )
    kb = back_cancel_kb("back_to_gift_config")
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(BuyGift.waiting_custom_signature)

@router.message(BuyGift.waiting_custom_signature)
async def custom_signature_input_handler(message: Message, state: FSMContext):
    text = message.text.strip().replace("|", "")
    if len(text) > 50:
        await message.answer("❌ Слишком длинный текст. Максимум 50 символов.")
        return
    
    await state.update_data(signature_text=text)
    await show_gift_config(message, state, is_edit=False)

@router.callback_query(F.data == "back_to_gift_config")
async def back_to_gift_config_handler(callback: CallbackQuery, state: FSMContext):
    await show_gift_config(callback.message, state)

@router.callback_query(F.data == "back_to_gifts_list")
async def back_to_gifts_list_handler(callback: CallbackQuery, state: FSMContext):
    await show_gift_list(callback.message, is_edit=True, state=state)

async def show_gift_list(message: Message, is_edit: bool = False, state: FSMContext = None):
    """Show the list of available gifts"""
    msg = "<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>Выберите подарок:</b>\n\n"
    
    for key, gift in GIFTS.items():
        msg += f"{gift['html_name']} - {gift['price']} <tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji> Stars\n\n"
        
    if is_edit:
        if message.photo:
            await message.edit_caption(caption=msg, reply_markup=gifts_kb(GIFTS), parse_mode="HTML")
        else:
            await message.edit_text(msg, reply_markup=gifts_kb(GIFTS), parse_mode="HTML")
    else:
        await message.answer(
            msg,
            reply_markup=gifts_kb(GIFTS),
            parse_mode="HTML"
        )

async def show_gift_config(message: Message, state: FSMContext, is_edit: bool = True):
    data = await state.get_data()
    gift_type = data.get("gift_type")
    gift = GIFTS.get(gift_type)
    is_anon = data.get("is_anonymous", False)
    sign_text = data.get("signature_text")
    recipient_username = data.get("recipient_username")
    
    target = f"@{recipient_username}" if recipient_username else "Себе"
    
    msg = (
        f"⚙️ <b>Параметры подарка:</b>\n\n"
        f"<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  Подарок: {gift['html_name']}\n"
        f"👤 Получатель: <b>{target}</b>\n"
        f"💰 Цена: <b>{gift['price']} <tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji> Stars</b>\n\n"
        f"🥷 <b>Анонимно:</b> {'Да' if is_anon else 'Нет'}\n"
    )
    
    # Only show signature if not anonymous
    show_signature = not is_anon
    if show_signature:
        msg += f"✍️ <b>Подпись:</b> {sign_text if sign_text else 'Без подписи'}\n"
    
    msg += f"\nНастройте параметры и нажмите кнопку ниже для оплаты."
    
    if is_edit:
        kb = gift_conf_kb(is_anon, show_signature, sign_text)
        if message.photo:
            await message.edit_caption(caption=msg, reply_markup=kb, parse_mode="HTML")
        else:
            await message.edit_text(msg, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(msg, reply_markup=gift_conf_kb(is_anon, show_signature, sign_text), parse_mode="HTML")

@router.callback_query(F.data.startswith("gift_"))
async def gift_selected(callback: CallbackQuery, state: FSMContext):
    """Handle gift selection and show config menu"""
    await callback.answer()
    
    gift_type = callback.data.split("_")[1]
    if not gift_type in GIFTS:
        return

    await state.update_data(gift_type=gift_type)
    await show_gift_config(callback.message, state)

@router.callback_query(F.data == "confirm_gift_payment")
async def confirm_gift_payment_handler(callback: CallbackQuery, state: FSMContext):
    """Show payment method selection for gift"""
    await callback.answer()
    
    data = await state.get_data()
    gift_type = data.get("gift_type")
    gift = GIFTS.get(gift_type)
    
    # Check UserBot balance
    from bot_app.userbot_manager import userbot_manager
    stars_balance = await userbot_manager.get_account_stars_balance()
    if stars_balance < gift['price']:
        await callback.answer(
            f"⚠️ В системе недостаточно звезд на данный момент ({stars_balance}). "
            "Пожалуйста, подождите пополнения или свяжитесь с поддержкой.",
            show_alert=True
        )
        await notify_admins(
            f"🚨 <b>НИЗКИЙ БАЛАНС ЗВЕЗД НА USERBOT!</b>\n"
            f"Пользователь хотел подарок: <b>{gift['name']}</b> ({gift['price']} звезд)\n"
            f"Баланс аккаунта: <b>{stars_balance} звезд</b>"
        )
        return

    from bot_app.keyboards import gift_payment_method_kb
    from bot_app.services import STARS_RATE
    
    gift_rub_price = 89
    
    text = (
        "💳 <b>Выберите способ оплаты подарка:</b>\n\n"
        "🌟 <b>Кошелёк (Звезды)</b> — оплата через инвойс в Telegram.\n"
        "🇷🇺 <b>Карта РФ / СБП</b> — оплата через Lava (89 ₽)."
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=gift_payment_method_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=gift_payment_method_kb(), parse_mode="HTML")

@router.callback_query(F.data == "pay_gift_stars")
async def pay_gift_stars_handler(callback: CallbackQuery, state: FSMContext):
    """Handle Star payment for gift (Original logic)"""
    await callback.answer()
    data = await state.get_data()
    gift_type = data.get("gift_type")
    gift = GIFTS.get(gift_type)
    if not gift: return

    recipient_username = data.get("recipient_username")
    is_anonymous = data.get("is_anonymous", False)
    signature_text = data.get("signature_text") if not is_anonymous else None
    
    recipient_str = f"RECIPIENT:{recipient_username}" if recipient_username else "RECIPIENT:self"
    anon_str = "ANON:TRUE" if is_anonymous else "ANON:FALSE"
    
    wallet_field = f"{recipient_str}|GIFT:{gift_type}|{anon_str}"
    if signature_text:
        wallet_field += f"|SIGN:{signature_text}"
    
    order_id = await create_order(
        callback.from_user.id, 0, gift['price'], 1, wallet_field,
        (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
        order_type="BUY_GIFT"
    )
    
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Оплата: {gift['name']}",
            description=gift['description'],
            payload=f"gift_order_{order_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=gift['name'], amount=gift['price'])],
            start_parameter="gift_purchase"
        )
        
        from bot_app.services import STARS_RATE
        price_rub = gift['price'] * STARS_RATE

        await callback.message.answer(
            f"✅ <b>Счет сформирован (Звезды)!</b>\n\n"
            f"Подарок: {gift['html_name']}\n"
            f"Цена: <b>{gift['price']} Stars</b>\n\n"
            f"Оплатите счет выше.",
            reply_markup=payment_actions_kb(None, order_id),
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")

@router.callback_query(F.data == "pay_gift_rub")
async def pay_gift_rub_handler(callback: CallbackQuery, state: FSMContext):
    """Handle RUB payment for gift (New logic)"""
    await callback.answer("⏳ Создаем ссылку...")
    data = await state.get_data()
    gift_type = data.get("gift_type")
    gift = GIFTS.get(gift_type)
    if not gift: return

    recipient_username = data.get("recipient_username")
    is_anonymous = data.get("is_anonymous", False)
    signature_text = data.get("signature_text") if not is_anonymous else None
    
    recipient_str = f"RECIPIENT:{recipient_username}" if recipient_username else "RECIPIENT:self"
    anon_str = "ANON:TRUE" if is_anonymous else "ANON:FALSE"
    
    wallet_field = f"{recipient_str}|GIFT:{gift_type}|{anon_str}"
    if signature_text:
        wallet_field += f"|SIGN:{signature_text}"
    
    # Fixed price for RUB payments as requested
    gift_rub_price = 89
    
    # Create order
    order_id = await create_order(
        callback.from_user.id,
        gift_rub_price,
        gift['price'], # Keep stars amount for fulfillment info
        1, 
        wallet_field,
        (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
        order_type="BUY_GIFT"
    )
    
    # Generate Lava payment link
    from bot_app.services import create_lava_payment
    pay_url = await create_lava_payment(gift_rub_price, order_id)
    from bot_app.database import update_order_payment
    await update_order_payment(order_id, "LAVA", pay_url)
    

    await callback.message.answer(
        f"✅ <b>Заявка на покупку подарка #{order_id} создана!</b>\n\n"
        f"Подарок: {gift['html_name']}\n"
        f"💰 К оплате: <b>{gift_rub_price} ₽</b>\n\n"
        f"Оплатите по ссылке ниже. После оплаты подарок будет отправлен автоматически.",
        reply_markup=payment_actions_kb(pay_url, order_id),
        parse_mode="HTML"
    )
    await state.clear()

async def send_gift_api(user_id: int, gift_id: str, text: str = None):
    """
    Call Telegram sendGift API via raw request
    """
    from aiogram.methods import TelegramMethod
    
    class SendGift(TelegramMethod[bool]):
        __returning__ = bool
        __api_method__ = "sendGift"
        
        user_id: int
        gift_id: str
        text: str | None = None
        text_parse_mode: str | None = None

        def hash_name(self) -> str:
            return f"sendGift:{self.user_id}:{self.gift_id}"

    method = SendGift(user_id=user_id, gift_id=gift_id, text=text)
    try:
        return await bot(method)
    except Exception as e:
        import logging
        logging.error(f"Error calling sendGift API: {e}")
        return False

@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query):
    """Handle pre-checkout query for gift purchase"""
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True
    )

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Handle successful payment and send gift"""
    payload = message.successful_payment.invoice_payload
    
    # Parse payload: "gift_order_{order_id}"
    if not payload.startswith("gift_order_"):
        return
    
    try:
        order_id = int(payload.split("_")[2])
        order = await get_order_details(order_id)
        
        if not order:
            await message.answer("❌ Заказ не найден.")
            return

        # Extract info from user_wallet field
        # "RECIPIENT:username|GIFT:type|ANON:TRUE|SIGN:text"
        wallet_field = order.get("user_wallet", "")
        recipient_username = None
        gift_type = None
        is_anonymous = False
        signature_text = None
        
        parts = wallet_field.split("|")
        for p in parts:
            if p.startswith("RECIPIENT:"):
                r = p.split(":")[1]
                if r != "self":
                    recipient_username = r
            elif p.startswith("GIFT:"):
                gift_type = p.split(":")[1]
            elif p.startswith("ANON:"):
                val = p.split(":")[1]
                is_anonymous = (val == "TRUE")
            elif p.startswith("SIGN:"):
                signature_text = p.split(":", 1)[1]
        
        gift = GIFTS.get(gift_type)
        if not gift:
            await message.answer("❌ Подарок не найден.")
            return

        from bot_app.services import process_successful_payment
        await process_successful_payment(order_id)
        # fulfill_order is called inside process_successful_payment
            
    except Exception as e:
        import logging
        logging.error(f"Error processing successful payment: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке заказа: {str(e)}")
            
    except Exception as e:
        import logging
        logging.error(f"Error processing successful_payment: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке заказа: {str(e)}")
