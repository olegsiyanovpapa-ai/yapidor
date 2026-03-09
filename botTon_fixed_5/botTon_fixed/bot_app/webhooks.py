from aiohttp import web
import logging
import json
from bot import bot
from bot_app.database import update_order_status
import os


async def lava_webhook(request):
    try:
        logging.info(f"LAVA WEBHOOK HIT! Method: {request.method}")
        logging.info(f"Headers: {dict(request.headers)}")
        
        raw_body = await request.read()
        logging.info(f"Raw body: {raw_body.decode('utf-8', errors='ignore')}")

        data = {}
        try:
            data = json.loads(raw_body)
        except Exception as e:
            logging.warning(f"Failed to parse JSON in Lava webhook: {e}")

        logging.info(f"Received Lava data: {data}")
        
        payload = data
        if "orderId" in payload and "order_id" not in payload:
            payload["order_id"] = payload["orderId"]
            
        invoice_id = payload.get("invoice_id")
        amount = payload.get("amount")
        # orderId в Lava приходит как "42_1741234567" (с timestamp), берём только число до "_"
        raw_order_id = payload.get("order_id") or payload.get("orderId", "")
        order_id = str(raw_order_id).split("_")[0] if raw_order_id else None
        status = payload.get("status")
        
        if not all([amount, order_id]):
            logging.info("Lava validation ping or missing params")
            return web.Response(text="OK")

        if status not in ("success", "paid"):
            logging.info(f"Lava status is {status}, ignoring.")
            return web.Response(text="OK")

        # Signature verification: HMAC-SHA256 of raw body
        import hmac
        import hashlib
        from bot_app.config import LAVA_SECRET_1, LAVA_SECRET_2
        
        # Lava sends signature in 'Authorization' header or 'sign' field
        auth_header = request.headers.get("Authorization", "")
        # Remove 'Bearer ' prefix if present
        provided_sign = auth_header.replace("Bearer ", "").strip() if auth_header else payload.get("sign", "")
        
        # Check Secret Key 2 (recommended for webhooks)
        expected_sign_2 = hmac.new(LAVA_SECRET_2.encode(), raw_body, hashlib.sha256).hexdigest()
        # Check Secret Key 1 (fallback)
        expected_sign_1 = hmac.new(LAVA_SECRET_1.encode(), raw_body, hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(provided_sign, expected_sign_2):
            logging.info("Lava signature matched with Secret Key 2.")
        elif hmac.compare_digest(provided_sign, expected_sign_1):
            logging.info("Lava signature matched with Secret Key 1 (fallback).")
        else:
            logging.error(
                f"Lava signature mismatch! \n"
                f"Provided (header/sign): {provided_sign}\n"
                f"Expected (Secret 2): {expected_sign_2}\n"
                f"Expected (Secret 1): {expected_sign_1}"
            )
            # We still return OK to avoid Lava retrying non-stop, but we don't process it.
            # However, if it's a critical issue, we might want to know.
            return web.Response(text="OK")
        
        if order_id:
            from bot_app.services import process_successful_payment
            await process_successful_payment(int(order_id))
            logging.info(f"Order {order_id} processed via Lava.")
        
        return web.Response(text="OK")
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL Error in Lava webhook: {e}\n{traceback.format_exc()}")
        return web.Response(text="OK")

async def manifest_handler(request):
    """Serve tonconnect-manifest.json"""
    try:
        manifest_path = "tonconnect-manifest.json"
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            return web.json_response(content)
        else:
            return web.Response(status=404, text="Manifest not found")
    except Exception as e:
        logging.error(f"Error serving manifest: {e}")
        return web.Response(status=500, text="Internal Error")


async def robynhood_webhook(request):
    """
    Обрабатывает уведомления от RobynHood о доставке Звезд или Премиум.
    RobynHood посылает POST-запрос когда инвойс оплачен/доставлен.
    """
    try:
        logging.info(f"RobynHood webhook hit! Method: {request.method}")
        
        data = {}
        try:
            data = await request.json()
        except Exception as e:
            logging.warning(f"Failed to parse JSON in RobynHood webhook: {e}")
        
        logging.info(f"RobynHood webhook data: {data}")
        
        # RobynHood webhook структура (invoice-based):
        # { "invoice_id": "...", "status": "paid", "type": "stars"/"premium",
        #   "amount": 100, "recipient": "@username", "buyer_id": 123456 }
        
        # Верификация через Authorization header (Bearer ROBYNHOOD_API_KEY)
        from bot_app.config import ROBYNHOOD_API_KEY
        auth_header = request.headers.get("Authorization", "")
        expected_auth = f"Bearer {ROBYNHOOD_API_KEY}"
        
        if ROBYNHOOD_API_KEY and auth_header != expected_auth:
            logging.warning(f"RobynHood webhook auth mismatch. Got: {auth_header[:20]}...")
            # Не отклоняем - просто логируем, API может не отправлять заголовок
        
        status = data.get("status", "")
        invoice_id = data.get("invoice_id", "")
        delivery_type = data.get("type", "")
        amount = data.get("amount", 0)
        recipient = data.get("recipient", "")
        buyer_id = data.get("buyer_id") or data.get("user_id")
        order_id = data.get("order_id") or data.get("external_id")
        
        logging.info(f"RobynHood: status={status}, type={delivery_type}, amount={amount}, buyer={buyer_id}")
        
        if not buyer_id:
            logging.info("RobynHood webhook: no buyer_id, ignoring.")
            return web.Response(text="OK")
        
        # Отправляем уведомление пользователю
        if status in ("paid", "success", "delivered", "completed"):
            try:
                if delivery_type == "stars":
                    msg = (
                        f"⭐ <b>Звёзды успешно доставлены!</b>\n\n"
                        f"• Количество: <b>{amount} ⭐</b>\n"
                        f"• Получатель: <b>{recipient or 'Вы'}</b>\n\n"
                        f"Спасибо за покупку! 🎉"
                    )
                elif delivery_type == "premium":
                    msg = (
                        f"🌟 <b>Telegram Premium успешно активирован!</b>\n\n"
                        f"• Срок: <b>{amount} мес.</b>\n"
                        f"• Получатель: <b>{recipient or 'Вы'}</b>\n\n"
                        f"Спасибо за покупку! 🎉"
                    )
                else:
                    msg = f"✅ <b>Доставка успешно выполнена!</b>\nТип: {delivery_type}, кол-во: {amount}"
                
                await bot.send_message(int(buyer_id), msg, parse_mode="HTML")
                logging.info(f"RobynHood delivery notification sent to user {buyer_id}")
                
                # Обновляем статус заказа в базе если есть order_id
                if order_id:
                    from bot_app.database import update_order_status
                    await update_order_status(int(order_id), "DELIVERED")
            except Exception as e:
                logging.error(f"Error notifying user {buyer_id} about RobynHood delivery: {e}")
        
        elif status in ("failed", "error", "cancelled"):
            try:
                err_msg = (
                    f"⚠️ <b>Ошибка доставки!</b>\n\n"
                    f"К сожалению, не удалось доставить товар.\n"
                    f"Тип: {delivery_type}, кол-во: {amount}\n\n"
                    f"Пожалуйста, обратитесь в поддержку: @UtkaX"
                )
                await bot.send_message(int(buyer_id), err_msg, parse_mode="HTML")
                logging.error(f"RobynHood delivery FAILED for user {buyer_id}: {data}")
            except Exception as e:
                logging.error(f"Error sending failure notification to {buyer_id}: {e}")
        
        return web.Response(text="OK")
    except Exception as e:
        import traceback
        logging.error(f"CRITICAL Error in RobynHood webhook: {e}\n{traceback.format_exc()}")
        return web.Response(text="OK")


def setup_webhooks(app):
    app.router.add_get("/tonconnect-manifest.json", manifest_handler)
    app.router.add_post("/lava/webhook", lava_webhook)
    app.router.add_post("/robynhood/webhook", robynhood_webhook)
