from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from bot_app.states import BuyStars
from bot_app.config import ORDER_LIFETIME
from bot_app.services import STARS_RATE, send_stars_via_robynhood, notify_admins, get_robynhood_stars_balance
from bot_app.database import create_order, update_order_payment, update_order_status
from bot_app.keyboards import stars_recipient_kb, back_cancel_kb, payment_actions_kb, stars_main_kb, stars_cancel_kb, main_kb
from bot_app.config import ADMINS
from bot_app.ton_utils import raw_to_user_friendly

router = Router()

@router.callback_query(F.data == "buy_stars")
async def buy_stars_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        f"<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars <b>Покупка Telegram Stars</b>\n\n"
        f"Курс: <b>{STARS_RATE} ₽</b> за 1 звезду.\n"
        f"Минимальное количество: 50 звезд.\n\n"
        f"Выберите, кому хотите купить звезды:",
        reply_markup=stars_recipient_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "stars_self")
async def stars_self_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(recipient_type="self", recipient_username=None)
    await callback.message.answer(
        f"<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  <b>Покупка звезд для себя</b>\n\n"
        f"Введите количество звезд (минимум 50):",
        reply_markup=back_cancel_kb("buy_stars"),
        parse_mode="HTML"
    )
    await state.set_state(BuyStars.waiting_stars_amount)

@router.callback_query(F.data == "stars_gift")
async def stars_gift_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(recipient_type="gift")
    await callback.message.answer(
        f"👤 <b>Подарок звезд другому пользователю</b>\n\n"
        f"Введите username получателя (без @):",
        reply_markup=back_cancel_kb("buy_stars"),
        parse_mode="HTML"
    )
    await state.set_state(BuyStars.waiting_recipient_username)

@router.message(BuyStars.waiting_recipient_username)
async def recipient_username_handler(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    
    if not username or len(username) < 3:
        await message.answer("❌ Некорректный username. Попробуйте еще раз:")
        return
    
    await state.update_data(recipient_username=username)
    await message.answer(
        f"✅ Получатель: @{username}\n\n"
        f"Введите количество звезд (минимум 50):",
        reply_markup=back_cancel_kb("stars_gift"), # Back to recipient input? Or buy_stars? 
        # Actually back to buy_stars is arguably cleaner but user might want to edit username.
        # But for now let's use stars_gift to allow re-entry of username?
        # No, stars_gift is a callback. If we callback "stars_gift", it resets state to waiting_recipient_username. Correct.
        parse_mode="HTML"
    )
    await state.set_state(BuyStars.waiting_stars_amount)

@router.message(BuyStars.waiting_stars_amount)
async def stars_amount_handler(message: Message, state: FSMContext):
    try:
        stars = int(message.text)
    except ValueError:
        await message.answer("❌ Введите целое число (например: 50 или 100).")
        return

    if stars < 50:
        await message.answer("❌ Минимальное количество для покупки — 50 звезд.")
        return

    # Check balance
    stars_balance = await get_robynhood_stars_balance()
    if stars_balance > 0 and stars_balance < stars:
        await message.answer(
            "⚠️ <b>В системе недостаточно звезд на данный момент.</b>\n"
            "Пожалуйста, попробуйте купить меньшее количество или подождите пополнения.\n"
            "Администраторы уже уведомлены.",
            parse_mode="HTML"
        )
        await notify_admins(
            f"🚨 <b>НИЗКИЙ БАЛАНС ЗВЕЗД (RobynHood)!</b>\n"
            f"Пользователь хочет: <b>{stars} звезд</b>\n"
            f"Баланс в API: <b>{stars_balance} звезд</b>"
        )
        return

    rub_amount = int(stars * STARS_RATE)
    
    # Get recipient info from state
    data = await state.get_data()
    recipient_type = data.get("recipient_type", "self")
    recipient_username = data.get("recipient_username")
    
    expires = datetime.utcnow() + timedelta(minutes=ORDER_LIFETIME)
    
    # Create order with recipient info
    order_id = await create_order(
        message.from_user.id, 
        rub_amount, 
        stars,
        STARS_RATE,
        f"TG_ID:{message.from_user.id}|RECIPIENT:{recipient_username or 'self'}",
        expires.isoformat(),
        order_type="BUY_STARS"
    )
    
    # Save order_id and stars info to state for later use
    await state.update_data(order_id=order_id, stars_amount=stars)
    
    # Create Free-Kassa Payment
    from bot_app.services import create_lava_payment
    pay_url = await create_lava_payment(rub_amount, order_id)
    await update_order_payment(order_id, "LAVA", pay_url)

    recipient_text = f"👤 Получатель: @{recipient_username}" if recipient_username else "<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Получатель: Вы"
    
    await message.answer(
        f"📝 <b>Заказ #{order_id} создан</b>\n"
        f"<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars Покупка: <b>{stars} звезд</b>\n"
        f"{recipient_text}\n"
        f"💵 К оплате: <b>{rub_amount} ₽</b>\n\n"
        f"Звезды будут начислены после оплаты.",
        reply_markup=payment_actions_kb(pay_url, order_id),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "cancel_stars_purchase")
async def cancel_stars_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Покупка отменена")
    await state.clear()
    await callback.message.answer(
        "❌ Покупка звезд отменена.",
        parse_mode="HTML"
    )
    is_admin = callback.from_user.id in ADMINS
    await callback.message.answer("🔙 Главное меню", reply_markup=main_kb(is_admin=is_admin), parse_mode="HTML")

# Redundant fulfillment logic removed (moved to services.py)
