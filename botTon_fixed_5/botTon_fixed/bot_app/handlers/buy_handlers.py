from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

from bot_app.states import BuyTON
from bot_app.config import ORDER_LIFETIME
from bot_app.services import get_ton_rate, get_bot_ton_balance, notify_admins
from bot_app.database import get_user_wallet, create_order, update_order_payment, get_last_orders, update_order_status, save_user
from bot_app.keyboards import payment_method_kb, payment_actions_kb, buy_confirm_kb, no_wallet_kb, main_kb
from bot_app.config import ADMINS
from bot_app import database
from bot_app.ton_utils import raw_to_user_friendly

router = Router()

@router.callback_query(F.data.startswith("pay_lava_"))
async def pay_lava_handler(callback: CallbackQuery):
    await callback.answer()
    try:
        order_id = int(callback.data.split("_")[2])
    except Exception:
        return
    from bot_app.database import get_order_details, update_order_payment
    from bot_app.services import create_lava_payment
    from bot_app.keyboards import payment_actions_kb
    order = await get_order_details(order_id)
    pay_url = None
    if order:
        pay_url = order.get("payment_url")
    if not pay_url:
        rub_amount = order.get("rub_amount") if order else None
        if rub_amount:
            pay_url = await create_lava_payment(int(rub_amount), order_id)
            if pay_url:
                await update_order_payment(order_id, "LAVA", pay_url)
    if pay_url:
        try:
            await callback.message.edit_reply_markup(reply_markup=payment_actions_kb(pay_url, order_id))
        except Exception:
            pass
        await callback.message.answer(f"Ссылка на оплату: {pay_url}")
    else:
        await callback.message.answer("Не удалось получить ссылку на оплату. Попробуйте создать заказ заново.")

@router.callback_query(F.data == "buy_ton")
async def buy_ton_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ Проверяем кошелёк...")
    try:
        # Check TON Connect wallet first
        from bot_app.ton_connect_manager import ton_connect_manager
        ton_connect_wallet = await ton_connect_manager.get_connected_wallet(callback.from_user.id)
        
        wallet = ton_connect_wallet or await get_user_wallet(callback.from_user.id)
        
        if not wallet:
            text = (
                "💼 <b>Кошелёк не подключен</b>\n\n"
                "Чтобы купить TON, сначала подключите кошелёк.\n"
                "Перейдите в раздел: <b>Меню -> Кошелёк -> Подключить кошелёк</b>"
            )
            kb = no_wallet_kb()
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return

        await state.update_data(user_wallet=wallet)
        
        friendly_address = raw_to_user_friendly(wallet)
        text = (
            f"💼 <b>Ваш подключенный кошелёк (HEX):</b>\n"
            f"<code>{wallet}</code>\n\n"
            f"✅ <b>Ваш адрес (Base64):</b>\n"
            f"<code>{friendly_address}</code>\n\n"
            f"Хотите получить TON на этот адрес?"
        )
        kb = buy_confirm_kb()
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        import logging
        logging.error(f"Error in buy_ton: {e}")
        await callback.message.answer(f"❌ Произошла ошибка. Попробуйте позже.")

@router.callback_query(F.data == "confirm_buy_wallet")
async def confirm_buy_wallet_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("✅ Подтверждено")
    text = "<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  <b>Введите количество TON, которое хотите купить:</b>"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(BuyTON.waiting_ton_buy)

@router.message(BuyTON.waiting_ton_buy)
async def ton_buy_input_handler(message: Message, state: FSMContext):
    try:
        ton_amount = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("❌ Введите число (например: 1.5 или 10).")
        return

    if ton_amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0.")
        return

    if ton_amount < 1:
        await message.answer(f"❌ Минимальная сумма покупки — 1 TON.")
        return

    if ton_amount > 100:
        await message.answer("❌ Максимальная сумма покупки — 100 TON.\nДля покупки большего объема свяжитесь с поддержкой.")
        return

    # Immediate feedback for the user
    status_msg = await message.answer("⏳ <b>Обработка запроса...</b>", parse_mode="HTML")

    try:
        # Check bot's wallet balance (now cached)
        bot_balance = await get_bot_ton_balance()
        if bot_balance < ton_amount + 0.1: # +0.1 for network fees buffer
            import logging
            logging.warning(f"Insufficient bot balance: {bot_balance} TON. User wanted {ton_amount} TON.")
            await status_msg.edit_text(
                "⚠️ <b>В системе недостаточно баланса на данный момент.</b>\n"
                "Пожалуйста, попробуйте позже или свяжитесь с поддержкой.\n"
                "Администраторы уже уведомлены о необходимости пополнения.",
                parse_mode="HTML"
            )
            await notify_admins(
                f"🚨 <b>НИЗКИЙ БАЛАНС TON!</b>\n"
                f"Пользователь хочет купить: <b>{ton_amount} TON</b>\n"
                f"Текущий баланс бота: <b>{bot_balance:.2f} TON</b>\n"
                f"Необходимо пополнить кошелек бота!"
            )
            return

        import logging
        logging.info(f"Processing BUY order: amount={ton_amount}, user_id={message.from_user.id}")

        # 1. Get rates
        try:
            market, buy_price, sell_price, *_ = await get_ton_rate(False)
            rub_amount = int(ton_amount * buy_price)
            
            # Temporary test price: 1 TON = 10 RUB
            if ton_amount == 1.0:
                rub_amount = 10
                logging.info("Test price applied: 1 TON = 10 RUB")
                
            logging.info(f"Rates fetched: buy_price={buy_price}, total={rub_amount} RUB")
        except Exception as e:
            logging.error(f"Error fetching rates: {e}")
            await status_msg.edit_text("❌ Ошибка при получении курса валют. Попробуйте позже.")
            return

        # 2. Get wallet from state (with fallback to DB / TON Connect)
        data = await state.get_data()
        wallet = data.get("user_wallet")
        if not wallet:
            logging.warning(f"User wallet missing in state for user {message.from_user.id}, trying fallback...")
            try:
                from bot_app.ton_connect_manager import ton_connect_manager
                wallet = await ton_connect_manager.get_connected_wallet(message.from_user.id)
            except Exception:
                wallet = None
            if not wallet:
                wallet = await get_user_wallet(message.from_user.id)
            if not wallet:
                logging.error(f"Wallet not found anywhere for user {message.from_user.id}")
                await status_msg.edit_text("❌ Ошибка: кошелёк не найден. Подключите кошелёк в разделе «Кошелёк» и попробуйте снова.")
                return
            # Save back to state for consistency
            await state.update_data(user_wallet=wallet)

        expires = datetime.utcnow() + timedelta(minutes=ORDER_LIFETIME)

        # 3. Create order in DB
        try:
            order_id = await create_order(message.from_user.id, rub_amount, ton_amount, buy_price, wallet, expires.isoformat())
            logging.info(f"Order created in DB: id={order_id}")
        except Exception as e:
            logging.error(f"Error creating order in DB: {e}")
            await status_msg.edit_text("❌ Ошибка базы данных при создании заказа. Попробуйте позже.")
            return
        
        # 4. Create payment invoice
        try:
            from bot_app.services import create_lava_payment
            pay_url = await create_lava_payment(rub_amount, order_id)
            if not pay_url:
                raise Exception("Lava API returned empty URL")
            
            await update_order_payment(order_id, "LAVA", pay_url)
            logging.info(f"Lava payment created: {pay_url}")
        except Exception as e:
            logging.error(f"Error creating Lava payment: {e}")
            await status_msg.edit_text("❌ Ошибка платежной системы. Попробуйте позже или свяжитесь с поддержкой.")
            # Optionally mark order as failed or delete it
            return

        # 5. Send success message
        friendly_address = raw_to_user_friendly(wallet)
        
        text = (
            f"📝 <b>Заявка #{order_id} создана</b>\n"
            f"<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  Купите: {ton_amount} TON\n"
            f"💵 Итого к оплате: <b>{rub_amount} ₽</b>\n\n"
            f"📥 <b>На кошелёк (HEX):</b>\n"
            f"<code>{wallet}</code>\n\n"
            f"✅ <b>Читаемый адрес (Base64):</b>\n"
            f"<code>{friendly_address}</code>\n\n"
            f"Оплатите заказ по ссылке ниже. Система автоматически подтвердит получение средств."
        )
        
        await status_msg.edit_text(
            text,
            reply_markup=payment_actions_kb(pay_url, order_id),
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        import logging
        logging.error(f"Critical error in ton_buy_input_handler: {e}\n{error_info}")
        try:
            await status_msg.edit_text("❌ Произошла ошибка при создании заказа. Пожалуйста, попробуйте еще раз.")
        except Exception:
            await message.answer("❌ Произошла ошибка при создании заказа. Пожалуйста, попробуйте еще раз.")

@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_id_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await update_order_status(order_id, "CANCELLED")
    await callback.answer("❌ Заказ отменен")
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=f"❌ Заказ #{order_id} отменен.")
        else:
            await callback.message.edit_text(f"❌ Заказ #{order_id} отменен.")
    except Exception:
        await callback.message.answer(f"❌ Заказ #{order_id} отменен.")
    is_admin = callback.from_user.id in ADMINS
    await callback.message.answer("🔙 Главное меню", reply_markup=main_kb(is_admin=is_admin), parse_mode="HTML")

@router.callback_query(F.data == "cancel_order")
async def cancel_order_generic_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отменено")
    data = await state.get_data()
    order_id = data.get("order_id")
    if order_id:
        await update_order_status(order_id, "CANCELLED")
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption="❌ Заказ отменен.")
        else:
            await callback.message.edit_text("❌ Заказ отменен.")
    except Exception:
        await callback.message.answer("❌ Заказ отменен.")
    is_admin = callback.from_user.id in ADMINS
    await callback.message.answer("🔙 Главное меню", reply_markup=main_kb(is_admin=is_admin), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("check_pay_"))
async def check_payment_handler(callback: CallbackQuery):
    await callback.answer("⏱ Оплата проверяется автоматически. Пожалуйста, подождите уведомления.", show_alert=True)

@router.callback_query(F.data == "history")
async def history_handler(callback: CallbackQuery):
    await callback.answer()
    rows = await get_last_orders(callback.from_user.id)
    if not rows:
        await callback.message.answer("📜 Истории пока нет.")
    else:
        msg = "📜 <b>Последние 5 операций:</b>\n\n"
        for r in rows:
            # r = (id, ton_amount, rub_amount, status, type)
            status = r[3]
            order_type = r[4] if len(r) > 4 else "BUY"
            
            icon = "🟢" if status == "PAID" else "🔴"
            type_label = "📥 Покупка" if order_type == "BUY" else "📤 Продажа"
            
            msg += f"#{r[0]} {icon} <b>{type_label}</b> | {r[1]} TON | {r[2]} ₽\n"
        await callback.message.answer(msg, parse_mode="HTML")
@router.callback_query(F.data.startswith("check_delivery_"))
async def check_delivery_user_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Проверяем...")
    
    from bot_app.services import fulfill_order
    # This will check if status is already DELIVERED and do nothing, or try to fulfill
    await fulfill_order(order_id)

@router.callback_query(F.data == "unified_history")
async def unified_history_handler(callback: CallbackQuery):
    # Just redirect to existing history for now
    await history_handler(callback)
