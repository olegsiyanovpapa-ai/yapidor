from aiogram import Router
from aiogram.types import CallbackQuery
import logging

router = Router()

@router.callback_query()
async def catch_all_callback(callback: CallbackQuery):
    """
    This handler catches ALL callback queries that were not handled by previous routers.
    It ensures the button stops spinning and informs the user/log.
    """
    logging.warning(f"UNHANDLED CALLBACK: {repr(callback.data)} from user {callback.from_user.id}")
    print(f"DEBUG: Unhandled data='{callback.data}' (len={len(callback.data)})")
    try:
        await callback.answer("⚠️ Кнопка не обработана (ошибка бота)", show_alert=True)
    except Exception as e:
        logging.error(f"Failed to answer callback: {e}")
