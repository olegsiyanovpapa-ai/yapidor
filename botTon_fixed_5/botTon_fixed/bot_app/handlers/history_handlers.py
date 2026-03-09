from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot_app.database import get_last_orders
from bot_app.keyboards import main_kb

router = Router()

@router.callback_query(F.data == "unified_history")
async def unified_history_handler(callback: CallbackQuery):
    """Display unified history with TON and Stars orders separated"""
    await callback.answer()
    
    rows = await get_last_orders(callback.from_user.id, limit=10)
    
    if not rows:
        await callback.message.answer(
            "📜 <b>История операций</b>\n\n"
            "У вас пока нет операций.",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
        return
    
    # Separate TON and Stars orders
    ton_orders = []
    stars_orders = []
    
    for r in rows:
        # r = (id, ton_amount, rub_amount, status, type)
        order_id = r[0]
        amount = r[1]
        rub = r[2]
        status = r[3]
        order_type = r[4] if len(r) > 4 else "BUY"
        
        icon = "🟢" if status == "PAID" else "🔴"
        
        if order_type == "BUY_STARS":
            stars_orders.append((order_id, amount, rub, status, icon))
        else:
            # BUY or SELL TON
            type_label = "Покупка" if order_type == "BUY" else "Продажа"
            ton_orders.append((order_id, amount, rub, status, icon, type_label))
    
    # Build message
    msg = "📜 <b>История операций</b>\n\n"
    
    # TON section
    if ton_orders:
        msg += "<tg-emoji emoji-id=\"5377620962390857342\">🎁</tg-emoji>  <b>TON</b>\n"
        for order_id, amount, rub, status, icon, type_label in ton_orders:
            msg += f"<blockquote>#{order_id} {icon} {type_label}\n{amount} TON • {rub} ₽</blockquote>\n"
    
    # Stars section
    if stars_orders:
        msg += "\n<tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars <b>Звезды</b>\n"
        for order_id, amount, rub, status, icon in stars_orders:
            msg += f"<blockquote>#{order_id} {icon} Покупка\n{int(amount)} <tg-emoji emoji-id=\"5267500801240092311\">🎁</tg-emoji>  Stars • {rub} ₽</blockquote>\n"
    
    await callback.message.answer(
        msg,
        parse_mode="HTML",
        reply_markup=main_kb()
    )
