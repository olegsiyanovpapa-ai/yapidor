from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot_app.config import ADMINS, SALE_ADMINS
from bot_app.database import get_admin_stats, get_all_orders, get_all_wallets, get_all_user_ids, clear_all_data
from bot_app.keyboards import admin_main_kb, admin_back_kb, admin_panel_back_kb, admin_clear_confirm_kb
import asyncio

router = Router()

def is_admin(user_id: int):
    return user_id in ADMINS or user_id in SALE_ADMINS

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    from bot_app.services import get_bot_ton_balance
    from bot_app.database import get_undelivered_paid_count
    
    balance = await get_bot_ton_balance()
    failed_count = await get_undelivered_paid_count()
    
    await message.answer(
        f"🛠 <b>Админ-панель</b>\n\n"
        f"💎 Баланс бота: <b>{balance:.2f} TON</b>\n"
        f"📦 Ошибок доставки: <b>{failed_count}</b>\n\n"
        f"Выберите раздел для управления:",
        reply_markup=admin_main_kb(failed_count),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав!", show_alert=True)
        return
    
    # Get last 5 orders for a quick preview
    last_orders = await get_all_orders(limit=5)
    orders_text = ""
    if last_orders:
        for o in last_orders:
            # id, user_id, rub_amount, ton_amount, status, type, created_at
            status_icon = "🟢" if o[4] == "PAID" else "⏳" if o[4] == "WAIT" else "🔴"
            orders_text += f"• #{o[0]} | {status_icon} {o[5]} | {o[2]} ₽\n"
    else:
        orders_text = "Заказов пока нет."

    from bot_app.services import get_bot_ton_balance
    from bot_app.database import get_undelivered_paid_count
    balance = await get_bot_ton_balance()
    failed_count = await get_undelivered_paid_count()

    admin_commands = (
        "<b>Доступные команды:</b>\n"
        "🔸 <code>/admin</code> — Вход в панель\n"
        "🔸 <code>/posted [текст]</code> — Рассылка сообщения\n"
        "🔸 <code>/user [id]</code> — Инфо пользователе\n"
        "🔸 <code>/shablon [текст]</code> — Обновить шаблон поста\n"
        "🔸 <code>/find_order [id]</code> — Поиск заказа\n"
        "🔸 <code>/top_users</code> — Топ покупателей\n"
    )

    text = (
        f"🛠 <b>Админ-панель Crypto Villa</b>\n\n"
        f"💎 Баланс: <b>{balance:.2f} TON</b>\n"
        f"📦 Ошибок: <b>{failed_count}</b>\n\n"
        f"<b>Последние 5 заказов:</b>\n"
        f"{orders_text}\n\n"
        f"{admin_commands}\n\n"
        f"Выберите раздел для управления:"
    )

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=admin_main_kb(failed_count),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text=text,
            reply_markup=admin_main_kb(failed_count),
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(Command("posted"))
async def broadcast_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    if not message.text:
        await message.answer("❌ Сообщение пустое.")
        return
    # Extract text after command, preserving premium emoji via entities
    space_idx = message.text.find(" ")
    if space_idx == -1 or space_idx == len(message.text) - 1:
        await message.answer("❌ Используйте: <code>/posted Ваш текст рассылки</code>", parse_mode="HTML")
        return
    broadcast_text = message.text[space_idx + 1 :]
    filtered_entities = []
    if message.entities:
        from aiogram.types import MessageEntity
        cut = space_idx + 1
        for ent in message.entities:
            if ent.type == "bot_command":
                continue
            if ent.offset >= cut:
                # shift entity to new text start
                new_ent = MessageEntity(
                    type=ent.type,
                    offset=ent.offset - cut,
                    length=ent.length,
                    url=getattr(ent, "url", None),
                    user=getattr(ent, "user", None),
                    language=getattr(ent, "language", None),
                    custom_emoji_id=getattr(ent, "custom_emoji_id", None)
                )
                filtered_entities.append(new_ent)
    user_ids = await get_all_user_ids()
    
    status_msg = await message.answer(f"🚀 Начинаю рассылку на {len(user_ids)} пользователей...")
    
    count = 0
    errors = 0
    
    for uid in user_ids:
        try:
            if filtered_entities:
                await message.bot.send_message(uid, broadcast_text, entities=filtered_entities)
            else:
                await message.bot.send_message(uid, broadcast_text)
            count += 1
            await asyncio.sleep(0.05)  # Prevent flood
        except Exception:
            errors += 1
            
    await status_msg.edit_text(f"✅ Рассылка завершена!\n\n👤 Доставлено: <b>{count}</b>\n❌ Ошибок: <b>{errors}</b>", parse_mode="HTML")

@router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer("⏳ Загрузка статистики...")
    
    stats = await get_admin_stats()
    
    msg = "<tg-emoji emoji-id=\"5231200819986047254\">🎁</tg-emoji>  <b>СТАТИСТИКА СИСТЕМЫ</b>\n"
    msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    # Orders by status
    msg += "<b>📋 Активность:</b>\n"
    status_map = {"WAIT": "⏳ Ожидание", "PAID": "✅ Оплачено", "CANCELLED": "❌ Отмена"}
    
    found_statuses = {row[0]: row for row in stats["by_status"]}
    for code, label in status_map.items():
        row = found_statuses.get(code, (code, 0, 0, 0))
        count = row[1]
        rub = row[2] or 0
        msg += f"• {label}: <b>{count}</b> шт. ({rub:,.0f} ₽)\n"
    
    # Profit
    p = stats["profit"]
    if p:
        # p = (buy_profit, sell_profit, premium_profit, stars_profit, buy_rub, sell_rub)
        buy_profit = p[0] or 0
        sell_profit = p[1] or 0
        premium_profit = p[2] or 0
        stars_profit = p[3] or 0
        total_profit = buy_profit + sell_profit + premium_profit + stars_profit
        
        msg += f"\n💰 <b>ЧИСТАЯ ПРИБЫЛЬ:</b>\n"
        msg += f"└ TON Покупка (+25%): <b>{buy_profit:,.2f} ₽</b>\n"
        msg += f"└ TON Продажа (-8%): <b>{sell_profit:,.2f} ₽</b>\n"
        msg += f"└ TG Premium (+20%): <b>{premium_profit:,.2f} ₽</b>\n"
        msg += f"└ Звезды/Подарки: <b>{stars_profit:,.2f} ₽</b>\n"
        msg += f"🔥 <b>ИТОГО ДОХОД: {total_profit:,.2f} ₽</b>\n"
    else:
        msg += "\n💰 Данных по прибыли пока нет."

    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_logs_paid")
@router.callback_query(F.data == "admin_logs_cancelled")
async def admin_logs_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    status_filter = "PAID" if "paid" in callback.data else "CANCELLED"
    label = "Успешные" if status_filter == "PAID" else "Отмененные"
    
    await callback.answer(f"⏳ Загрузка: {label}...")
    
    orders = await get_all_orders(status_filter=status_filter, limit=20)
    
    if not orders:
        msg = f"📭 <b>{label} заказов не найдено.</b>\n\n"
        if status_filter == "CANCELLED":
            msg += "<i>Система записывает отмены при нажатии кнопки «Отмена» пользователем.</i>"
    else:
        msg = f"📜 <b>{label} закупки (последние 20):</b>\n\n"
        for o in orders:
            # id, user_id, rub_amount, ton_amount, status, type, created_at
            status = o[4]
            order_type = o[5]
            
            status_icon = "🟢" if status == "PAID" else "🔴"
            type_icon = "📥" if order_type == "BUY" else "📤"
            type_label = "ПОКУПКА" if order_type == "BUY" else "ПРОДАЖА"
            
            msg += f"#{o[0]} | {status_icon} {type_icon} {type_label} | {o[3]} TON | {o[2]:,.0f} ₽\n└ User: <code>{o[1]}</code>\n"
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_wallets")
async def admin_wallets_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    await callback.answer("⏳ Загрузка списка кошельков...")
    
    wallets_data = await get_all_wallets()
    manual = wallets_data["manual"]
    tc = wallets_data["ton_connect"]
    
    msg = "💼 <b>ПОДКЛЮЧЕННЫЕ КОШЕЛЬКИ</b>\n"
    msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    seen_users = {}
    for uid, addr in tc:
        if addr:
            seen_users[uid] = f"🔗 <code>{addr[:10]}...{addr[-8:]}</code> (Connect)"
    
    for uid, addr in manual:
        if uid not in seen_users and addr:
            seen_users[uid] = f"✏️ <code>{addr[:10]}...{addr[-8:]}</code> (Manual)"
    
    if not seen_users:
        msg += "📭 Активных кошельков не найдено."
    else:
        msg += f"Всего в базе: <b>{len(seen_users)}</b> чел.\n\n"
        limit = 25
        for i, (uid, info) in enumerate(list(seen_users.items())[:limit]):
            msg += f"{i+1}. 🆔 <code>{uid}</code>\n└ {info}\n"
        
        if len(seen_users) > limit:
            msg += f"\n<i>...и еще {len(seen_users)-limit} пользователей.</i>"
    
    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.message(Command("user"))
async def user_info_handler(message: Message):
    if not is_admin(message.from_user.id): return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Используйте: <code>/user [ID]</code>", parse_mode="HTML")
        return
    
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID.")
        return

    from bot_app.database import get_user_full_data
    data = await get_user_full_data(uid)
    if not data:
        await message.answer("❌ Пользователь не найден в базе.")
        return
    
    u = data['user']
    orders = data['orders']
    
    orders_text = ""
    for o in orders:
        status_icon = "🟢" if o['status'] == "PAID" else "⏳" if o['status'] == "WAIT" else "🔴"
        orders_text += f"• #{o['id']} | {status_icon} {o['type']} | {o['rub_amount']} ₽ | {o['created_at'][:16].replace('T', ' ')}\n"

    msg = (
        f"👤 <b>Профиль пользователя: {u['username'] or 'Без ника'}</b>\n"
        f"🆔 ID: <code>{u['user_id']}</code>\n"
        f"📅 Регистрация: {u['created_at'][:10]}\n\n"
        f"💼 <b>Кошелек (Manual):</b> <code>{u['default_wallet'] or 'Нет'}</code>\n\n"
        f"📜 <b>Последние 10 заказов:</b>\n"
        f"{orders_text or 'Заказов не было.'}"
    )
    
    await message.answer(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_pending_payouts")
async def admin_pending_payouts_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer("⏳ Загрузка выплат...")
    
    from bot_app.database import get_orders_by_status_and_type
    # SELL orders that are PAID (user sent TON to bot) but bot hasn't sent RUB (manual)
    orders = await get_orders_by_status_and_type("PAID", "SELL", limit=20)
    
    if not orders:
        msg = "✅ <b>Все выплаты (SELL) обработаны!</b>\n\nНет активных заявок на отправку средств пользователям."
    else:
        msg = "💳 <b>ОЖИДАЮТ ВЫПЛАТЫ (SELL):</b>\n\n"
        for o in orders:
            # Include unique MEMO comment if present to облегчить сверку
            memo = o.get('payment_id') or 'N/A'
            msg += (
                f"• #{o['id']} | 🆔 <code>{o['user_id']}</code>\n"
                f"└ <b>{o['rub_amount']} ₽</b> | {o['user_wallet']}\n"
                f"└ MEMO: <code>{memo}</code>\n"
            )
        msg += "\n<i>Все эти заказы PAID, значит TON от юзера получен. Нужно отправить рубли.</i>"

    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_wait_orders")
async def admin_wait_orders_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer("⏳ Загрузка...")
    
    from bot_app.database import get_orders_by_status_and_type
    # Orders stuck in WAIT status
    orders = await get_orders_by_status_and_type("WAIT", limit=20)
    
    if not orders:
        msg = "✅ <b>Зависших заказов (WAIT) нет.</b>"
    else:
        msg = "⏳ <b>ЗАКАЗЫ В ОЖИДАНИИ (WAIT):</b>\n\n"
        for o in orders:
            msg += f"• #{o['id']} | {o['type']} | <b>{o['rub_amount']} ₽</b>\n└ 🆔 <code>{o['user_id']}</code> | {o['created_at'][:16].replace('T', ' ')}\n"
        msg += "\n<i>Если юзер оплатил, а статус WAIT — проверьте Lava или кошелек.</i>"

    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.message(Command("top_users"))
async def top_users_handler(message: Message):
    if not is_admin(message.from_user.id): return
    
    from bot_app.database import get_top_buyers
    buyers = await get_top_buyers()
    
    msg = "🏆 <b>ТОП ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    
    msg += "💰 <b>Топ по покупкам:</b>\n"
    if buyers:
        for i, b in enumerate(buyers, 1):
            msg += f"{i}. <code>{b['user_id']}</code> | {b['username'] or '???'} | <b>{b['total_rub']:,} ₽</b>\n"
    else:
        msg += "Пока нет данных.\n"
        
    await message.answer(msg, parse_mode="HTML")

@router.message(Command("find_order"))
async def find_order_handler(message: Message, order_id_override: int = None):
    viewer_id = message.from_user.id if isinstance(message, Message) else message.chat.id
    if not is_admin(viewer_id): return
    
    if order_id_override:
        oid = order_id_override
    else:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("❌ Используйте: <code>/find_order [ID]</code>", parse_mode="HTML")
            return
        try:
            oid = int(parts[1])
        except ValueError:
            await message.answer("❌ Некорректный ID заказа.")
            return

    from bot_app.database import get_order_by_id
    o = await get_order_by_id(oid)
    if not o:
        msg = "❌ Заказ не найден."
        if order_id_override:
            await message.edit_text(msg)
        else:
            await message.answer(msg)
        return
    
    status_icon = "🟢" if o['status'] == "DELIVERED" else "🔵" if o['status'] == "PAID" else "⏳" if o['status'] == "WAIT" else "🔴"
    
    error_text = ""
    if o['status'] == 'PAID' and o['delivery_error']:
        error_text = f"\n\n🚨 <b>ОШИБКА ДОСТАВКИ:</b>\n<i>{o['delivery_error']}</i>"

    msg = (
        f"🔍 <b>Информация о заказе #{o['id']}</b>\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👤 Юзер: 🆔 <code>{o['user_id']}</code>\n"
        f"Тип: {o['type']}\n"
        f"Статус: {status_icon} <b>{o['status']}</b>\n"
        f"Сумма: <b>{o['rub_amount']} ₽</b>\n"
        f"TON: <b>{o['ton_amount']}</b>\n"
        f"Кошелек: <code>{o['user_wallet'] or 'Нет'}</code>\n"
        f"Комментарий: <code>{o['comment'] or 'Нет'}</code>\n"
        f"Создан: {o['created_at'].replace('T', ' ')}"
        f"{error_text}"
    )
    
    from bot_app.keyboards import admin_payout_actions_kb
    kb = admin_payout_actions_kb(o['id'], show_repeat=(o['status'] == 'PAID'))
    
    if order_id_override:
        await message.edit_text(msg, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(msg, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_clear_stats")
async def admin_clear_stats_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    msg = (
        "🗑 <b>Очистка данных</b>\n\n"
        "Выберите, что очистить:"
    )
    from bot_app.keyboards import admin_clear_menu_kb
    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, reply_markup=admin_clear_menu_kb(), parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, reply_markup=admin_clear_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_clear_stats_confirmed")
async def admin_clear_stats_confirmed_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    
    await clear_all_data()
    await callback.answer("✅ Статистика и заказы очищены!", show_alert=True)
    
    # Return to admin panel (fresh one)
    await admin_panel_callback(callback)

@router.callback_query(F.data == "admin_clear_all")
async def admin_clear_all_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await clear_all_data()
    await callback.answer("✅ Очищены все заказы и служебные счетчики", show_alert=True)
    await admin_panel_callback(callback)

@router.callback_query(F.data == "admin_clear_wait")
async def admin_clear_wait_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    from bot_app.database import clear_orders_by_status
    await clear_orders_by_status("WAIT")
    await callback.answer("✅ Очищены WAIT заказы", show_alert=True)
    await admin_panel_callback(callback)

@router.callback_query(F.data == "admin_clear_paid")
async def admin_clear_paid_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    from bot_app.database import clear_orders_by_status
    await clear_orders_by_status("PAID")
    await callback.answer("✅ Очищены PAID заказы", show_alert=True)
    await admin_panel_callback(callback)

@router.callback_query(F.data == "admin_clear_cancelled")
async def admin_clear_cancelled_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    from bot_app.database import clear_orders_by_status
    await clear_orders_by_status("CANCELLED")
    await callback.answer("✅ Очищены CANCELLED заказы", show_alert=True)
    await admin_panel_callback(callback)


@router.callback_query(F.data == "admin_logs_failed")
async def admin_logs_failed_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.answer("⏳ Загрузка ошибок...")
    
    from bot_app.database import get_failed_payouts
    orders = await get_failed_payouts(limit=20)
    
    if not orders:
        msg = "✅ <b>Ошибок доставки не обнаружено.</b>\n\nВсе оплаченные заказы успешно доставлены."
    else:
        msg = "🚨 <b>НЕВЫПОЛНЕННЫЕ ЗАКАЗЫ:</b>\n\n"
        for o in orders:
            # id, user_id, rub_amount, ton_amount, status, type, created_at, delivery_error
            error = o['delivery_error'] or "Неизвестная ошибка"
            msg += (
                f"• #{o['id']} | {o['type']} | {o['ton_amount']} TON\n"
                f"└ Ошибка: <i>{error}</i>\n"
                f"└ User: <code>{o['user_id']}</code>\n\n"
            )
        msg += "<i>Используйте /find_order [ID] чтобы повторить доставку.</i>"
    
    await callback.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_repeat_delivery_"))
async def admin_repeat_delivery_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = int(callback.data.split("_")[-1])
    
    await callback.answer("🚀 Перезапуск доставки...")
    from bot_app.services import fulfill_order
    await fulfill_order(order_id)
    
    # Refresh order info
    await find_order_handler(callback.message, order_id_override=order_id)

@router.callback_query(F.data.startswith("admin_payout_done_"))
async def admin_payout_done_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    order_id = int(callback.data.split("_")[-1])
    
    from bot_app.database import update_order_status, set_delivery_error
    await update_order_status(order_id, 'DELIVERED')
    await set_delivery_error(order_id, None)
    
    await callback.answer("✅ Статус изменен на DELIVERED", show_alert=True)
    await find_order_handler(callback.message, order_id_override=order_id)

