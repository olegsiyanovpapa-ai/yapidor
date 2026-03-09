from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from bot_app.states import SellTON
from bot_app.config import ORDER_LIFETIME, TON_SENDER_WALLET, SALE_ADMINS
from bot_app.services import get_ton_rate
from bot_app.database import create_order, update_order_status
from bot_app.keyboards import (
    main_kb, sell_confirm_kb, payout_method_kb, banks_kb, 
    admin_confirm_payout_kb, user_confirm_receipt_kb
)
from bot_app.ton_utils import generate_ton_payment_link, raw_to_user_friendly
import re
import random
import string

router = Router()

@router.callback_query(F.data == "sell_ton")
async def sell_ton_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📉 <b>Продажа TON</b>\n\nВведите количество TON, которое хотите продать:", parse_mode="HTML")
    await state.set_state(SellTON.waiting_ton_amount)

@router.message(SellTON.waiting_ton_amount)
async def sell_ton_amount_handler(message: Message, state: FSMContext):
    try:
        ton = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число (например, 10 или 5.5).")
        return

    if ton < 10:
        await message.answer("❌ Минимальная сумма 10 TON.")
        return

    market, buy_price, sell_price, *_ = await get_ton_rate(False)
    rub_to_receive = round(ton * sell_price, 2)
    
    await state.update_data(ton=ton, rate=sell_price, rub=rub_to_receive)
    
    await message.answer(
        f"📉 <b>Продажа {ton} TON</b>\n\n"
        f"<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  Текущий курс: <b>{sell_price} ₽</b>\n"
        f"💰 Вы получите: <b>{rub_to_receive} ₽</b>\n\n"
        f"Вы действительно хотите продать TON?",
        reply_markup=sell_confirm_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "confirm_sell_amount")
async def confirm_sell_amount_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  <b>Выберите способ получения выплаты:</b>",
        reply_markup=payout_method_kb(),
        parse_mode="HTML"
    )
    await state.set_state(SellTON.waiting_method)

@router.callback_query(F.data.startswith("sell_method_"), SellTON.waiting_method)
async def sell_method_handler(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2] # 'card' or 'phone'
    await state.update_data(payout_method=method)
    
    await callback.answer()
    await callback.message.edit_text(
        "🏦 <b>Выберите ваш банк:</b>",
        reply_markup=banks_kb(),
        parse_mode="HTML"
    )
    await state.set_state(SellTON.waiting_bank)

@router.callback_query(F.data.startswith("sell_bank_"), SellTON.waiting_bank)
async def sell_bank_handler(callback: CallbackQuery, state: FSMContext):
    bank = callback.data.replace("sell_bank_", "")
    await state.update_data(bank=bank)
    
    data = await state.get_data()
    method = data.get("payout_method")
    
    await callback.answer()
    if method == "card":
        prompt = "<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  <b>Введите номер вашей карты РФ</b> (16 цифр):"
    else:
        prompt = "📱 <b>Введите номер телефона</b> для СБП (например, +79001234567):"
        
    await callback.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(SellTON.waiting_requisites)

@router.message(SellTON.waiting_requisites)
async def sell_ton_requisites_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    method = data.get("payout_method")
    bank = data.get("bank")
    requisite = message.text.strip().replace(" ", "")
    
    # Validation
    if method == "card":
        if not re.match(r"^\d{16}$", requisite):
            await message.answer("❌ <b>Ошибка!</b> Введите 16 цифр номера карты.")
            return
    else:
        # Basic phone validation (+7 or 8 followed by 10 digits)
        if not re.match(r"^(\+7|8)\d{10}$", requisite):
            await message.answer("❌ <b>Ошибка!</b> Введите номер телефона в формате +79001234567.")
            return

    # Update state data
    await state.update_data(requisite=requisite)
    
    # Combined wallet/requisite field for DB: "BANK:Sber|METHOD:Phone|VAL:requisite"
    method_label = "Карта" if method == "card" else "Телефону (СБП)"
    wallet_info = f"BANK:{bank}|METHOD:{method_label}|VAL:{requisite}"
    
    # Generate unique alphanumeric comment (e.g., 5 random letters/digits)
    unique_comment = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    ton = data.get("ton")
    rub = data.get("rub")
    rate = data.get("rate")
    expires = datetime.utcnow() + timedelta(minutes=ORDER_LIFETIME)
    
    order_id = await create_order(
        message.from_user.id, rub, ton, rate, 
        wallet_info, 
        expires.isoformat(), 
        order_type="SELL",
        payment_id=unique_comment
    )
    
    # Wallet to receive TON (Our wallet)
    our_wallet_raw = TON_SENDER_WALLET
    
    if not our_wallet_raw:
        await message.answer("❌ <b>Ошибка конфигурации!</b> Кошелёк для приёма TON не настроен. Свяжитесь с поддержкой.")
        return
    
    # Generate Deeplink with unique comment
    pay_link = generate_ton_payment_link(our_wallet_raw, ton, comment=unique_comment)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📱 Отправить через TON", url=pay_link)
    kb.button(text="✅ Проверить получение", callback_data=f"check_ton_pay_{order_id}")
    kb.adjust(1)

    await message.answer(
        f"✅ <b>Заявка #{order_id} создана!</b>\n\n"
        f"Чтобы получить <b>{rub} ₽</b>, вам нужно отправить <b>{ton} TON</b> на наш кошелёк.\n\n"
        f"Для этого нажмите кнопку ниже. В кошельке уже будет введен адрес, сумма и <b>комментарий `{unique_comment}`</b> (это важно!).",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("check_ton_pay_"))
async def check_ton_payment(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    await callback.answer("⏳ Проверяем транзакцию...")
    
    from bot_app.database import get_order_details, update_order_status
    order = await get_order_details(order_id)
    
    if not order:
        await callback.message.answer("❌ Заказ не найден.")
        return
    
    # Verify on-chain incoming transfer by unique comment and amount
    unique_comment = order.get("payment_id")
    ton_amount = float(order.get("ton_amount", 0))
    from bot_app.services import verify_ton_incoming
    ok = False
    try:
        ok = await verify_ton_incoming(TON_SENDER_WALLET, ton_amount, unique_comment)
    except Exception:
        ok = False
    
    if not ok:
        await callback.message.answer(
            "⏳ Транзакция еще не найдена в сети TON.\n"
            "Подождите 15–60 секунд и нажмите «Проверить получение» снова.",
            parse_mode="HTML"
        )
        return
    
    # 1. Update status when verified
    await update_order_status(order_id, "PAID")
    
    # Notify sales channel
    from bot_app.services import notify_sales_channel
    await notify_sales_channel(order_id, order)
    
    # 2. Notify Admins
    user_id = callback.from_user.id
    username = callback.from_user.username or "Unknown"
    wallet_info = order.get("user_wallet", "")
    ton_amount = order.get("ton_amount")
    rub_amount = order.get("rub_amount")
    unique_comment = order.get("payment_id", "N/A")
    
    # Parse wallet_info: "BANK:Sber|METHOD:Phone|VAL:requisite"
    bank_name = "Неизвестно"
    payout_method = "Неизвестно"
    requisite = wallet_info
    
    if "|" in wallet_info:
        parts = wallet_info.split("|")
        for p in parts:
            if p.startswith("BANK:"): bank_name = p.split(":")[1]
            elif p.startswith("METHOD:"): payout_method = p.split(":")[1]
            elif p.startswith("VAL:"): requisite = p.split(":")[1]

    admin_msg = (
        f"🚨 <b>Новая заявка на продажу TON!</b>\n\n"
        f"👤 Продавец: @{username} (ID: <code>{user_id}</code>)\n"
        f"<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  Сумма: <b>{ton_amount} TON</b>\n"
        f"💰 К выплате: <b>{rub_amount} ₽</b>\n"
        f"🏦 Банк: <b>{bank_name}</b>\n"
        f"🛠 Способ: <b>{payout_method}</b>\n"
        f"<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  Реквизиты: <code>{requisite}</code>\n"
        f"💬 Комментарий (MEMO): <code>{unique_comment}</code>\n\n"
        f"Проверьте поступление TON и переведите рубли."
    )
    
    from bot import bot
    for admin_id in SALE_ADMINS:
        try:
            await bot.send_message(admin_id, admin_msg, reply_markup=admin_confirm_payout_kb(order_id), parse_mode="HTML")
        except Exception as e:
            import logging
            logging.error(f"Failed to notify admin {admin_id}: {e}")

    # 3. Notify User
    await callback.message.edit_text(
        f"✅ <b>TON получены!</b>\n\n"
        f"Ваша заявка #{order_id} передана в обработку.\n"
        f"💰 Ожидайте поступления <b>{rub_amount} ₽</b> на {bank_name} ({payout_method}) в течение от 30 минут до 24 часов.\n\n"
        f"🆘 Если у вас возникли вопросы, напишите в поддержку: @UtkaX с хэштегом #HelpTon",
        parse_mode="HTML"
    )
@router.callback_query(F.data.startswith("admin_payout_done_"))
async def admin_payout_done_handler(callback: CallbackQuery):
    order_id = int(callback.data.replace("admin_payout_done_", ""))
    
    from bot_app.database import get_order_details, update_order_status
    order = await get_order_details(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return
    
    # Check if already processed
    if order.get("status") == "COMPLETED":
        await callback.answer("✅ Уже подтверждено.", show_alert=True)
        return

    # 1. Update DB
    await update_order_status(order_id, "COMPLETED")
    
    # 2. Parse Requisites for detailed notification
    wallet_info = order.get("user_wallet", "")
    bank_name = "Неизвестно"
    payout_method = "Неизвестно"
    requisite = wallet_info
    
    if "|" in wallet_info:
        parts = wallet_info.split("|")
        for p in parts:
            if p.startswith("BANK:"): bank_name = p.split(":")[1]
            elif p.startswith("METHOD:"): payout_method = p.split(":")[1]
            elif p.startswith("VAL:"): requisite = p.split(":")[1]

    # 3. Notify User
    user_id = order.get("user_id")
    rub_amount = order.get("rub_amount")
    
    user_msg = (
        f"✅ <b>Средства отправлены!</b>\n\n"
        f"Выплата по вашей заявке #{order_id} была произведена.\n\n"
        f"💰 Сумма: <b>{rub_amount} ₽</b>\n"
        f"🏦 Банк: <b>{bank_name}</b>\n"
        f"<tg-emoji emoji-id=\"5445353829304387411\">🎁</tg-emoji>  Реквизиты: <code>{requisite}</code>\n\n"
        f"Проверьте поступление на счет. Спасибо, что выбрали нас!"
    )
    
    from bot import bot
    try:
        await bot.send_message(user_id, user_msg, reply_markup=user_confirm_receipt_kb(order_id), parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Failed to notify user {user_id} about payout: {e}")

    # 4. Update Admin Message
    await callback.message.edit_text(
        f"✅ <b>Выплата по заказу #{order_id} подтверждена.</b>\n\n"
        f"Пользователь получил уведомление.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Подтверждено!")

@router.callback_query(F.data.startswith("user_receipt_done_"))
async def user_receipt_done_handler(callback: CallbackQuery):
    order_id = int(callback.data.replace("user_receipt_done_", ""))
    
    from bot_app.database import get_order_details, update_order_status
    order = await get_order_details(order_id)
    
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return
    
    # Check if already processed
    if order.get("status") == "SUCCESS":
        await callback.answer("✅ Уже подтверждено.", show_alert=True)
        return

    # 1. Update DB to final status
    await update_order_status(order_id, "SUCCESS")
    
    # 2. Extract info for admin notification
    user_id = callback.from_user.id
    username = callback.from_user.username or "Unknown"
    
    # 3. Notify Admins (Gratitude)
    admin_msg = (
        f"🙏 <b>Благодарность получена!</b>\n\n"
        f"Пользователь @{username} (ID: <code>{user_id}</code>) подтвердил получение средств по заказу #{order_id}.\n"
        f"✅ Сделка успешно завершена."
    )
    
    from bot_app.config import SALE_ADMINS
    from bot import bot
    for admin_id in SALE_ADMINS:
        try:
            await bot.send_message(admin_id, admin_msg, parse_mode="HTML")
        except Exception as e:
            import logging
            logging.error(f"Failed to notify admin {admin_id} about user gratitude: {e}")

    # 4. Final User View
    await callback.message.edit_text(
        f"✅ <b>Спасибо за подтверждение!</b>\n\n"
        f"Мы рады, что средства дошли. Ждем вас снова! 🙏✨",
        parse_mode="HTML"
    )
    await callback.answer("🙏 Спасибо за сделку!")
