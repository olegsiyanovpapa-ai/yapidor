from aiogram.fsm.state import State, StatesGroup

class BuyTON(StatesGroup):
    waiting_wallet = State()
    waiting_ton_buy = State()

class SellTON(StatesGroup):
    waiting_ton_amount = State()
    waiting_method = State()
    waiting_bank = State()
    waiting_requisites = State()

class ExchangeStars(StatesGroup):
    confirm_wallet = State()
    waiting_stars_amount = State()

class BuyStars(StatesGroup):
    waiting_recipient_username = State()
    waiting_stars_amount = State()

class BuyGift(StatesGroup):
    waiting_recipient_username = State()
    waiting_custom_signature = State()

class BuyPremium(StatesGroup):
    waiting_duration = State()
    waiting_recipient_type = State()
    waiting_recipient_username = State()

