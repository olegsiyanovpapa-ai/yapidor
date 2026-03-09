from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from bot_app.states import BuyPremium
from bot_app.config import ORDER_LIFETIME
from bot_app.services import PREMIUM_TON_COSTS, get_premium_prices_rub, send_premium_via_robynhood, notify_admins, get_robynhood_stars_balance
from bot_app.database import create_order, update_order_payment, update_order_status, get_order_details
from bot_app.keyboards import premium_duration_kb, premium_recipient_kb, back_cancel_kb, payment_actions_kb

router = Router()

@router.callback_query(F.data == "buy_premium")
async def buy_premium_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        prices = await get_premium_prices_rub()
        text = (
            "<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>Покупка Telegram Premium</b>\n\n"
            "Выберите длительность подписки (цена в рублях по курсу TON + 20%):"
        )
        kb = premium_duration_kb(prices)
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Error in buy_premium_start: {e}")
        await callback.message.answer("❌ Ошибка при загрузке цен Premium.")

@router.callback_query(F.data == "premium_self")
async def premium_self_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    duration = data.get("duration_months")
    price = data.get("price_rub")
    
    await create_premium_order(callback, state, duration, price, "self")

@router.callback_query(F.data == "premium_gift")
async def premium_gift_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    text = (
        "👤 <b>Подарок Premium другому</b>\n\n"
        "Введите username получателя (без @):"
    )
    kb = back_cancel_kb("buy_premium")
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(BuyPremium.waiting_recipient_username)

@router.callback_query(F.data.startswith("premium_"))
async def premium_duration_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    if len(data) < 2: return
    
    duration = data[1]
    if duration in ["self", "gift"]: return # Handled above
    
    try:
        duration_months = int(duration)
    except ValueError:
        return

    await state.update_data(duration_months=duration_months)
    await callback.answer()
    
    prices = await get_premium_prices_rub()
    price = prices.get(duration_months, 0)
    await state.update_data(price_rub=price)

    text = (
        f"<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>Telegram Premium на {duration_months} мес.</b>\n"
        f"<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  Стоимость: <b>{price} ₽</b>\n\n"
        "Выберите, кому хотите приобрести подписку:"
    )
    kb = premium_recipient_kb()
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.message(BuyPremium.waiting_recipient_username)
async def premium_recipient_username_handler(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    if len(username) < 3:
        await message.answer("❌ Некорректный username. Попробуйте еще раз:")
        return
        
    data = await state.get_data()
    duration = data.get("duration_months")
    price = data.get("price_rub")
    
    await create_premium_order(message, state, duration, price, username)

async def create_premium_order(event, state, duration, price, recipient):
    user_id = event.from_user.id
    
    # Check balance
    stars_balance = await get_robynhood_stars_balance()
    # Premium roughly costs 450-1000 stars depending on duration
    required_stars = 1000 if duration == 12 else 500
    if stars_balance > 0 and stars_balance < required_stars:
        text = (
            "⚠️ <b>В системе недостаточно баланса для оформления Premium на данный момент.</b>\n"
            "Пожалуйста, попробуйте позже. Администраторы уже уведомлены."
        )
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        
        await notify_admins(
            f"🚨 <b>НИЗКИЙ БАЛАНС ДЛЯ PREMIUM (RobynHood)!</b>\n"
            f"Пользователь хотел: <b>Premium {duration} мес.</b>\n"
            f"Баланс в API: <b>{stars_balance} звезд</b>"
        )
        return

    expires = datetime.utcnow() + timedelta(minutes=ORDER_LIFETIME)
    
    order_id = await create_order(
        user_id,
        price,
        duration, # Store duration in ton_amount field
        0, # Rate not applicable
        f"TG_ID:{user_id}|PREMIUM:{duration}|RECIPIENT:{recipient}",
        expires.isoformat(),
        order_type="BUY_PREMIUM"
    )
    
    from bot_app.services import create_lava_payment
    pay_url = await create_lava_payment(price, order_id)
    await update_order_payment(order_id, "LAVA", pay_url)
    
    recipient_text = f"👤 Получатель: @{recipient}" if recipient != "self" else "<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  Получатель: Вы"
    
    text = (
        f"📝 <b>Заказ #{order_id} создан</b>\n"
        f"<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  Покупка: <b>Telegram Premium ({duration} мес.)</b>\n"
        f"{recipient_text}\n"
        f"💵 К оплате: <b>{price} ₽</b>\n\n"
        f"Подписка будет активна после оплаты."
    )
    

    if isinstance(event, CallbackQuery):
        kb = payment_actions_kb(pay_url, order_id)
        if event.message.photo:
            await event.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=payment_actions_kb(pay_url, order_id), parse_mode="HTML")
        
    await state.clear()

# Backend fulfillment
# Redundant fulfillment logic removed (moved to services.py)
