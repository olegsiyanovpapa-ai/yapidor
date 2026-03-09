```python
from aiohttp import web
import logging
import json
import hashlib
from bot import bot
from bot_app.config import LAVA_SECRET_2
from bot_app.services import process_successful_payment


async def lava_webhook(request):
    try:
        logging.info(f"Lava webhook hit! Method: {request.method}")

        raw_body = await request.read()
        body_text = raw_body.decode("utf-8", errors="ignore")

        logging.info(f"Lava raw body: {body_text}")

        try:
            payload = json.loads(body_text)
        except Exception:
            logging.error("Invalid JSON from Lava")
            return web.Response(text="OK")

        logging.info(f"Lava payload: {payload}")

        # -------- Проверка подписи --------
        auth_header = request.headers.get("Authorization", "")
        provided_sign = auth_header.replace("Bearer ", "").strip()

        if not provided_sign:
            provided_sign = payload.get("sign", "")

        if not provided_sign:
            logging.error("No Lava signature provided")
            return web.Response(text="OK")

        expected_sign = hashlib.sha256(
            raw_body + LAVA_SECRET_2.encode()
        ).hexdigest()

        if provided_sign != expected_sign:
            logging.error(
                f"Lava signature mismatch!\n"
                f"Provided: {provided_sign}\n"
                f"Expected: {expected_sign}"
            )
            return web.Response(text="OK")

        logging.info("Lava signature verified")

        # -------- Проверка данных --------
        status = payload.get("status")
        amount = payload.get("amount")

        raw_order_id = payload.get("order_id") or payload.get("orderId")

        if not raw_order_id:
            logging.error("No order_id in webhook")
            return web.Response(text="OK")

        order_id = int(str(raw_order_id).split("_")[0])

        if status not in ("success", "paid"):
            logging.info(f"Ignoring status: {status}")
            return web.Response(text="OK")

        logging.info(f"Payment confirmed: order {order_id}, amount {amount}")

        # -------- Выполнение заказа --------
        await process_successful_payment(order_id)

        logging.info(f"Order {order_id} processed successfully")

        return web.Response(text="OK")

    except Exception as e:
        import traceback
        logging.error(f"Lava webhook error: {e}\n{traceback.format_exc()}")
        return web.Response(text="OK")
```
