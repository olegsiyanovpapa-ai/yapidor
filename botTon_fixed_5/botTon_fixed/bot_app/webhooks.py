```python
async def lava_webhook(request):
    try:
        import hashlib
        import logging
        import json
        from bot_app.config import LAVA_SECRET_1, LAVA_SECRET_2
        from bot_app.services import process_successful_payment

        logging.info(f"Lava webhook hit! Method: {request.method}")

        raw_body = await request.read()
        body_text = raw_body.decode("utf-8", errors="ignore")
        logging.info(f"Lava raw body: {body_text}")

        try:
            payload = json.loads(body_text)
        except Exception as e:
            logging.error(f"Lava JSON parse error: {e}")
            return web.Response(text="OK")

        logging.info(f"Lava payload: {payload}")

        # ---- Получаем подпись ----
        auth_header = request.headers.get("Authorization", "")
        provided_sign = auth_header.replace("Bearer ", "").strip()

        if not provided_sign:
            provided_sign = payload.get("sign", "")

        if not provided_sign:
            logging.error("Lava webhook: signature missing")
            return web.Response(text="OK")

        # ---- Формируем строку подписи ----
        payload_for_sign = dict(payload)
        payload_for_sign.pop("sign", None)

        sorted_items = sorted(payload_for_sign.items())

        sign_string = "".join(str(v) for k, v in sorted_items)

        expected_sign_2 = hashlib.sha256(
            (sign_string + LAVA_SECRET_2).encode()
        ).hexdigest()

        expected_sign_1 = hashlib.sha256(
            (sign_string + LAVA_SECRET_1).encode()
        ).hexdigest()

        if provided_sign == expected_sign_2:
            logging.info("Lava signature matched with SECRET 2")
        elif provided_sign == expected_sign_1:
            logging.info("Lava signature matched with SECRET 1")
        else:
            logging.error(
                f"Lava signature mismatch!\n"
                f"Provided: {provided_sign}\n"
                f"Expected2: {expected_sign_2}\n"
                f"Expected1: {expected_sign_1}"
            )
            return web.Response(text="OK")

        # ---- Получаем данные платежа ----
        amount = payload.get("amount")
        status = payload.get("status")

        raw_order_id = payload.get("order_id") or payload.get("orderId", "")
        order_id = str(raw_order_id).split("_")[0] if raw_order_id else None

        if not order_id:
            logging.error("Lava webhook: order_id missing")
            return web.Response(text="OK")

        if status not in ("success", "paid"):
            logging.info(f"Lava webhook ignored status: {status}")
            return web.Response(text="OK")

        logging.info(
            f"Lava payment confirmed: order={order_id}, amount={amount}"
        )

        # ---- Обрабатываем оплату ----
        await process_successful_payment(int(order_id))

        logging.info(f"Lava order processed: {order_id}")

        return web.Response(text="OK")

    except Exception as e:
        import traceback
        logging.error(
            f"Lava webhook CRITICAL ERROR: {e}\n{traceback.format_exc()}"
        )
        return web.Response(text="OK")
```
