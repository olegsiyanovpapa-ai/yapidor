import logging
import os
from aiohttp import web
from bot import bot, dp
from bot_app.database import init_db
from bot_app.handlers import base_handlers, buy_handlers, sell_handlers, admin_handlers, stars_handlers, history_handlers, gift_handlers, premium_handlers

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    
    # Pre-fetch rates in background
    from bot_app.services import get_ton_rate
    asyncio.create_task(get_ton_rate(force_live=True))
    
    # Include modular routers
    dp.include_router(base_handlers.router)
    dp.include_router(buy_handlers.router)
    dp.include_router(sell_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(stars_handlers.router)
    dp.include_router(history_handlers.router)
    dp.include_router(gift_handlers.router)
    dp.include_router(premium_handlers.router)
    from bot_app.handlers import debug_handlers, channel_handlers
    dp.include_router(debug_handlers.router)
    dp.include_router(channel_handlers.router)

    # Setup Webhook Server
    from bot_app.webhooks import setup_webhooks
    app = web.Application()
    setup_webhooks(app)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Webhook server started on port {port}")

    logging.info("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped")
