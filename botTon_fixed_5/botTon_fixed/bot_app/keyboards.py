from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_kb(is_admin=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="TON", callback_data="menu_ton", icon_custom_emoji_id="5377620962390857342")
    kb.button(text="Звезды", callback_data="menu_stars", icon_custom_emoji_id="5393261188878451091")
    kb.button(text="Купить Premium", callback_data="buy_premium", icon_custom_emoji_id="5393261188878451091")
    kb.button(text="Купить подарок", callback_data="buy_gift", icon_custom_emoji_id="5308052937556136027")
    kb.button(text="📜 История", callback_data="unified_history")
    kb.button(text="📄 Политика Конфиденциальности", callback_data="privacy_policy")
    if is_admin:
        kb.button(text="Админ-панель", callback_data="admin_panel", icon_custom_emoji_id="5336771760366821915")
    kb.adjust(1)
    return kb.as_markup()

def privacy_policy_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back_to_initial")
    return kb.as_markup()

def ton_main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить TON", callback_data="buy_ton", icon_custom_emoji_id="5377620962390857342")
    kb.button(text="Продать TON", callback_data="sell_ton", icon_custom_emoji_id="5429518319243775957")
    kb.button(text="📜 История", callback_data="history")
    kb.button(text="Кошелёк", callback_data="my_wallet", icon_custom_emoji_id="5336771760366821915")
    kb.button(text="🔙 Назад", callback_data="back_to_initial")
    kb.adjust(1)
    return kb.as_markup()

def stars_main_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить Звезды", callback_data="buy_stars", icon_custom_emoji_id="5393261188878451091")
    kb.button(text="🔙 Назад", callback_data="back_to_initial")
    kb.adjust(1)
    return kb.as_markup()

def payment_method_kb(order_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Карта РФ / СБП", callback_data=f"pay_lava_{order_id}")
    kb.button(text="Отмена", callback_data="cancel_order", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def wallet_kb(wallet, is_ton_connect=False):
    kb = InlineKeyboardBuilder()
    if is_ton_connect:
        kb.button(text="Отключить кошелёк", callback_data="disconnect_wallet", icon_custom_emoji_id="5210952531676504517")
        kb.button(text="🔗 Переподключить", callback_data="connect_tonkeeper")
        kb.button(text="✏️ Изменить вручную", callback_data="change_wallet")
    elif wallet:
        kb.button(text="Удалить адрес", callback_data="delete_wallet", icon_custom_emoji_id="5210952531676504517")
        kb.button(text="🔗 Подключить Tonkeeper", callback_data="connect_tonkeeper")
        kb.button(text="✏️ Изменить вручную", callback_data="change_wallet")
    else:
        kb.button(text="🔗 Подключить Tonkeeper", callback_data="connect_tonkeeper")
        kb.button(text="✏️ Ввести вручную", callback_data="change_wallet")
    
    kb.button(text="🔙 Назад", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()

def payment_actions_kb(pay_url, order_id):
    kb = InlineKeyboardBuilder()
    if pay_url:
        kb.button(text="💳 Оплатить картой РФ / СБП (Lava)", url=pay_url)
    else:
        kb.button(text="💳 Оплатить картой РФ / СБП (Lava)", callback_data=f"pay_lava_{order_id}")
    kb.button(text="Отменить заказ", callback_data=f"cancel_order_{order_id}", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def buy_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data="confirm_buy_wallet")
    kb.button(text="Отмена", callback_data="back_to_main", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(2)
    return kb.as_markup()

def sell_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить сумму", callback_data="confirm_sell_amount")
    kb.button(text="Отмена", callback_data="back_to_main", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def no_wallet_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Перейти в Кошелёк", callback_data="my_wallet", icon_custom_emoji_id="5336771760366821915")
    kb.button(text="Отмена", callback_data="back_to_main", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def admin_main_kb(failed_count: int = 0):
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    
    failed_text = "⚠️ Ошибки доставки"
    if failed_count > 0:
        failed_text = f"🚨 Ошибки ({failed_count})"
    kb.button(text=failed_text, callback_data="admin_logs_failed")
    
    kb.button(text="💳 Ожидают выплат (SELL)", callback_data="admin_pending_payouts")
    kb.button(text="⏳ Невыполненные (WAIT)", callback_data="admin_wait_orders")
    kb.button(text="✅ Успешные закупки", callback_data="admin_logs_paid")
    kb.button(text="Отмененные", callback_data="admin_logs_cancelled", icon_custom_emoji_id="5210952531676504517")
    kb.button(text="Кошельки", callback_data="admin_wallets", icon_custom_emoji_id="5336771760366821915")
    kb.button(text="🗑 Очистить статистику", callback_data="admin_clear_stats")
    kb.button(text="🔙 Назад в меню", callback_data="back_to_initial")
    kb.adjust(1)
    return kb.as_markup()

def order_status_kb(order_id: int, status: str):
    """Keyboard for users to check/repeat delivery if stuck in PAID but not DELIVERED"""
    kb = InlineKeyboardBuilder()
    if status == 'PAID':
        kb.button(text="🔄 Проверить/Повторить доставку", callback_data=f"check_delivery_{order_id}")
    kb.button(text="🔙 В главное меню", callback_data="back_to_initial")
    kb.adjust(1)
    return kb.as_markup()

def admin_back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад в админку", callback_data="admin_panel")
    return kb.as_markup()

def admin_panel_back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад в меню", callback_data="back_to_initial")
    return kb.as_markup()

def admin_clear_confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, очистить всё", callback_data="admin_clear_stats_confirmed")
    kb.button(text="❌ Отмена", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()

def admin_clear_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Очистить ВСЕ заказы", callback_data="admin_clear_all")
    kb.button(text="⏳ Очистить WAIT", callback_data="admin_clear_wait")
    kb.button(text="✅ Очистить PAID", callback_data="admin_clear_paid")
    kb.button(text="Очистить CANCELLED", callback_data="admin_clear_cancelled", icon_custom_emoji_id="5210952531676504517")
    kb.button(text="🔙 Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()

def stars_recipient_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить себе", callback_data="stars_self", icon_custom_emoji_id="5308052937556136027")
    kb.button(text="👤 Купить другому", callback_data="stars_gift")
    kb.button(text="Отменить", callback_data="back_to_initial", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def back_cancel_kb(back_callback: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data=back_callback)
    kb.button(text="Отмена", callback_data="cancel_stars_purchase", icon_custom_emoji_id="5210952531676504517") # Keep generic cancel for now or rename?
    kb.adjust(1)
    return kb.as_markup()

def stars_cancel_kb():
    # Deprecated but kept for compatibility if needed, but we should replace usages.
    # Or just alias it.
    return back_cancel_kb("buy_stars")

def gift_recipient_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить себе", callback_data="gift_self", icon_custom_emoji_id="5308052937556136027")
    kb.button(text="👤 Купить другому", callback_data="gift_other")
    kb.button(text="Отменить", callback_data="back_to_initial", icon_custom_emoji_id="5210952531676504517")
    kb.adjust(1)
    return kb.as_markup()

def gifts_kb(gifts=None):
    """Keyboard for selecting Telegram gifts"""
    kb = InlineKeyboardBuilder()
    
    if gifts:
        for key, gift in gifts.items():
            kb.button(text=f"{gift['name']}", callback_data=f"gift_{key}", icon_custom_emoji_id=gift.get('emoji_id'))
    else:
        # Fallback for compatibility
        kb.button(text='Сердце Ван Лав', callback_data="gift_heart", icon_custom_emoji_id="5224628072619216265")
        kb.button(text='Мишка Ван Лав', callback_data="gift_bear", icon_custom_emoji_id="5226661632259691727")
        kb.button(text='Новогодняя Елка', callback_data="gift_tree", icon_custom_emoji_id="5345935030143196497")
        kb.button(text='Новогодний Мишка', callback_data="gift_bear_newyear", icon_custom_emoji_id="5379850840691476775")
        kb.button(text='Мишка 8 Марта', callback_data="gift_bear_8march", icon_custom_emoji_id="5289761157173775507")
    
    kb.button(text="🔙 Назад", callback_data="buy_gift")
    kb.adjust(1)
    return kb.as_markup()

def gift_conf_kb(is_anonymous=False, show_signature=True, signature_text=None):
    kb = InlineKeyboardBuilder()
    
    anon_text = "🥷 Анонимно: Да" if is_anonymous else "👤 Анонимно: Нет"
    kb.button(text=anon_text, callback_data="toggle_anonymity")
    
    if show_signature:
        sign_display = signature_text if signature_text else "Без подписи"
        kb.button(text=f"✍️ Подпись: {sign_display}", callback_data="change_signature")
    
    kb.button(text="✅ Подтвердить и выбрать способ", callback_data="confirm_gift_payment")
    kb.button(text="🔙 Назад к списку", callback_data="back_to_gifts_list")
    kb.adjust(1)
    return kb.as_markup()

def gift_payment_method_kb(order_id: int = None):
    kb = InlineKeyboardBuilder()
    kb.button(text="Кошелёк (Звезды)", callback_data="pay_gift_stars", icon_custom_emoji_id="5308052937556136027")
    kb.button(text="💳 Карта РФ / СБП (89 ₽)", callback_data="pay_gift_rub")
    kb.button(text="🔙 Назад", callback_data="back_to_gift_config")
    kb.adjust(1)
    return kb.as_markup()

def signature_selection_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Юзернейм", callback_data="sign_username")
    kb.button(text="✏️ Свой текст", callback_data="sign_custom")
    kb.button(text="Без подписи", callback_data="sign_none", icon_custom_emoji_id="5210952531676504517")
    kb.button(text="🔙 Назад", callback_data="back_to_gift_config")
    kb.adjust(1)
    return kb.as_markup()

def payout_method_kb():
    """Choice between Card or Phone/SBP for payout"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Карта", callback_data="sell_method_card")
    kb.button(text="📱 Номер телефона (СБП)", callback_data="sell_method_phone")
    kb.button(text="🔙 Назад", callback_data="sell_ton")
    kb.adjust(1)
    return kb.as_markup()

def banks_kb():
    """Selection of popular RF banks"""
    kb = InlineKeyboardBuilder()
    banks = ["Сбербанк", "Тинькофф", "Альфа-Банк", "ВТБ", "Райффайзен", "Газпромбанк", "Озон Банк"]
    for bank in banks:
        kb.button(text=bank, callback_data=f"sell_bank_{bank}")
    kb.button(text="🔙 Назад", callback_data="confirm_sell_amount")
    kb.adjust(2)
    return kb.as_markup()

def admin_payout_actions_kb(order_id: int, show_repeat: bool = False):
    kb = InlineKeyboardBuilder()
    if show_repeat:
        kb.button(text="🚀 Повторить доставку", callback_data=f"admin_repeat_delivery_{order_id}")
    kb.button(text="✅ Средства отправлены", callback_data=f"admin_payout_done_{order_id}")
    kb.button(text="🔙 Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()

def user_confirm_receipt_kb(order_id: int):
    """Button for user to confirm they received the funds"""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Средства получил", callback_data=f"user_receipt_done_{order_id}")
    return kb.as_markup()

def premium_duration_kb(prices=None):
    """Keyboard for selecting Telegram Premium duration"""
    kb = InlineKeyboardBuilder()
    
    if prices:
        kb.button(text=f"3️⃣ Месяца — {prices.get(3, 0)} ₽", callback_data="premium_3")
        kb.button(text=f"6️⃣ Месяцев — {prices.get(6, 0)} ₽", callback_data="premium_6")
        kb.button(text=f"1️⃣2️⃣ Месяцев — {prices.get(12, 0)} ₽", callback_data="premium_12")
    else:
        # Fallback (Static)
        kb.button(text="3️⃣ Месяца — 1290 ₽", callback_data="premium_3")
        kb.button(text="6️⃣ Месяцев — 2150 ₽", callback_data="premium_6")
        kb.button(text="1️⃣2️⃣ Месяцев — 3100 ₽", callback_data="premium_12")
        
    kb.button(text="🔙 Назад", callback_data="back_to_initial")
    kb.adjust(1)
    return kb.as_markup()

def premium_recipient_kb():
    """Keyboard for selecting Premium recipient"""
    kb = InlineKeyboardBuilder()
    kb.button(text="Купить себе", callback_data="premium_self", icon_custom_emoji_id="5308052937556136027")
    kb.button(text="👤 Купить другому", callback_data="premium_gift")
    kb.button(text="🔙 Назад", callback_data="buy_premium")
    kb.adjust(1)
    return kb.as_markup()
