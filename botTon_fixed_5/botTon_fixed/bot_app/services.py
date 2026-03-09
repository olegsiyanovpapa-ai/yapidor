import aiohttp
import logging
from lxml import html
# No extra imports needed from config here for now

logger = logging.getLogger(__name__)

# Simple in-memory cache
_rate_cache = {
    "rate": None,
    "timestamp": 0,
    "fetching": False
}

_balance_cache = {
    "balance": 0.0,
    "timestamp": 0,
    "fetching": False
}

# Persistent TonCenterClient to avoid re-initialization overhead
_ton_client = None

# 1 Star = 1.38 RUB (Sell rate to user)
STARS_RATE = 1.38

# Premium prices in USD bases (Specific prices requested by user)
PREMIUM_USD_COSTS = {
    3: 11.99,
    6: 15.99,
    12: 28.99
}

# Fallback TON costs if USD logic fails
PREMIUM_TON_COSTS = {
    3: 4.0,
    6: 6.0,
    12: 11.0
}

async def fetch_fragment_premium_prices():
    """
    Парсит цены Telegram Premium в TON с Fragment.com.
    """
    url = "https://fragment.com/premium"
    xpaths = {
        12: "/html/body/div[2]/main/form/div[2]/div/div/label[1]/div/div[2]",
        6: "/html/body/div[2]/main/form/div[2]/div/div/label[2]/div/div[2]",
        3: "/html/body/div[2]/main/form/div[2]/div/div/label[3]/div/div[2]"
    }
    prices = {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"Fragment.com returned status {response.status}")
                    return None
                
                content = await response.text()
                tree = html.fromstring(content)
                
                for months, xpath in xpaths.items():
                    elements = tree.xpath(xpath)
                    if elements:
                        text = elements[0].text_content().strip()
                        # Оставляем только цифры и точку (например "11.95 TON" -> 11.95)
                        import re
                        match = re.search(r"(\d+\.?\d*)", text)
                        if match:
                            prices[months] = float(match.group(1))
                        else:
                            logger.warning(f"Could not parse price text from Fragment: {text}")
                    else:
                        logger.warning(f"XPath not found for {months} months on Fragment")
        
        if len(prices) == 3:
            return prices
        return None
    except Exception as e:
        logger.error(f"Error fetching prices from Fragment: {e}")
        return None

async def get_premium_prices_rub():
    """
    Рассчитывает стоимость Premium в рублях на основе USD цен + 20% наценки.
    """
    # 1. Получаем актуальный курс TON (RUB и USD)
    # rate_data = (market_rub, buy, sell, market_usd)
    rate_data = await get_ton_rate()
    market_rub = rate_data[0]
    market_usd = rate_data[3]
    
    # 2. Рассчитываем курс USD/RUB
    if market_usd > 0 and market_rub > 0:
        usd_rub_rate = market_rub / market_usd
    else:
        # Fallback если API лежит (примерно 90-100 руб)
        usd_rub_rate = 95.0
        logger.warning(f"Using fallback USD/RUB rate: {usd_rub_rate}")

    prices = {}
    import math
    for months, usd_cost in PREMIUM_USD_COSTS.items():
        # База в рублях = цена в USD * курс USD/RUB
        base_rub = usd_cost * usd_rub_rate
        # Наценка 20%
        with_markup = base_rub * 1.20
        
        # Округление вверх до 10 рублей для красивого вида
        prices[months] = int(math.ceil(with_markup / 10.0) * 10)
        
    return prices

import asyncio
import time

async def fetch_and_cache_rates():
    async def fetch_coingecko():
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "the-open-network", "vs_currencies": "rub,usd"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    ton_data = data["the-open-network"]
                    return float(ton_data["rub"]), float(ton_data["usd"])
                return None, None

    async def fetch_tonapi():
        url = "https://tonapi.io/v2/rates?tokens=ton&currencies=rub,usd"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    prices = data["rates"]["TON"]["prices"]
                    return float(prices["RUB"]), float(prices["USD"])
                return None, None

    market_price = None
    market_usd = None
    try:
        # Try parallel fetch
        results = await asyncio.gather(
            fetch_coingecko(),
            fetch_tonapi(),
            return_exceptions=True
        )
        for res in results:
            if isinstance(res, tuple) and res[0] is not None:
                market_price, market_usd = res
                break
    except Exception as e:
        logger.error(f"Rate fetch error: {e}")

    if market_price:
        sell_price = round(market_price * 0.92, 2)
        buy_price = round(market_price * 1.25, 2)
        result = (round(market_price, 2), buy_price, sell_price, round(market_usd or 0, 2))
        _rate_cache["rate"] = result
        _rate_cache["timestamp"] = time.time()
        
    _rate_cache["fetching"] = False


async def get_ton_rate(force_live: bool = False):
    """Получает курс TON к RUB."""
    current_time = time.time()
    
    # Refresh if older than 5 minutes or forced
    needs_refresh = force_live or (current_time - _rate_cache.get("timestamp", 0) > 300)
    
    if needs_refresh and not _rate_cache.get("fetching"):
        _rate_cache["fetching"] = True
        if force_live:
            await fetch_and_cache_rates()
        else:
            asyncio.create_task(fetch_and_cache_rates())

    # Return whatever we have in cache immediately
    if _rate_cache.get("rate"):
        return _rate_cache["rate"]
            
    # If no cache at all, return defaults instead of waiting
    return 600.0, 750.0, 550.0, 7.0 # Default fallback values

async def create_lava_payment(amount: int, order_id: int):
    """
    Создает ссылку на оплату в Lava.ru.
    """
    import aiohttp
    import hmac
    import hashlib
    import json
    import time
    from .config import LAVA_PROJECT_ID, LAVA_API_KEY, LAVA_SECRET_1, LAVA_SECRET_2, LAVA_WEBHOOK

    def _jwt_expired(token: str) -> bool | None:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            import base64, json as _json
            def b64url_pad(s: str) -> bytes:
                pad = (-len(s)) % 4
                return base64.urlsafe_b64decode(s + ("=" * pad))
            payload = _json.loads(b64url_pad(parts[1]).decode())
            exp = payload.get("exp")
            if not exp:
                return None
            return time.time() > float(exp)
        except Exception:
            return None

    # Быстрая валидация реквизитов перед запросом
    missing = []
    if not LAVA_PROJECT_ID: missing.append("LAVA_PROJECT_ID")
    if not LAVA_API_KEY: missing.append("LAVA_API_KEY")
    if not LAVA_SECRET_1: missing.append("LAVA_SECRET_1")
    if not LAVA_SECRET_2: missing.append("LAVA_SECRET_2")
    if not LAVA_WEBHOOK: missing.append("LAVA_WEBHOOK")
    if missing:
        logger.error(f"Lava config missing: {', '.join(missing)}")
        return None

    exp_state = _jwt_expired(LAVA_API_KEY)
    if exp_state is True:
        logger.error("Lava API key appears expired (JWT exp < now)")
        return None

    url = "https://api.lava.ru/business/invoice/create"

    unique_order_id = f"{order_id}_{int(time.time())}"

    # Порядок полей важен для подписи!
    from .config import LAVA_SUCCESS_URL, LAVA_FAIL_URL
    payload = {
        "sum": float(amount),
        "orderId": unique_order_id,
        "shopId": LAVA_PROJECT_ID,
        "hookUrl": LAVA_WEBHOOK,
        "expire": 15,
        "comment": f"Оплата заказа #{order_id}"
    }
    if LAVA_SUCCESS_URL:
        payload["successUrl"] = LAVA_SUCCESS_URL
    if LAVA_FAIL_URL:
        payload["failUrl"] = LAVA_FAIL_URL

    # Считаем подпись от payload (рекомендуемый метод - подпись в заголовке)
    json_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature = hmac.new(
        LAVA_SECRET_1.encode("utf-8"),
        json_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Signature": signature,
    }
    # Некоторые инсталляции LAVA требуют только подпись HMAC без Bearer-токена.
    # Если токен всё же выдан — добавим его, но это опционально.
    if LAVA_API_KEY:
        headers["Authorization"] = f"Bearer {LAVA_API_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=json_str.encode("utf-8"), headers=headers) as resp:
                raw = await resp.text()
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {}
                if resp.status == 200 and data.get("data") and data["data"].get("url"):
                    return data["data"]["url"]
                else:
                    if resp.status == 401:
                        logger.error("Lava returned 401 Unauthenticated. Verify Signature (Secret 1), project shopId and payload format. Bearer may be unnecessary.")
                    else:
                        logger.error(f"Lava error (status={resp.status}): {raw}")
                    return None
    except Exception as e:
        import traceback
        logger.error(f"Failed to create Lava invoice: {e}\n{traceback.format_exc()}")
        return None


async def send_ton_to_user(wallet_address: str, amount_ton: float, comment: str):
    """
    Отправляет TON пользователю с кошелька бота через tonutils (WalletV5R1 / W5) с использованием TonAPI.
    """
    from .config import TON_SENDER_MNEMONIC, TONAPI_KEY
    import logging

    if not TON_SENDER_MNEMONIC:
        logger.error("TON_SENDER_MNEMONIC not set in .env")
        return False, "Ошибка конфигурации кошелька"

    try:
        from tonutils.client import TonapiClient
        from tonutils.wallet import WalletV5R1

        mnemonics_list = TON_SENDER_MNEMONIC.strip().split()
        # Initialize TonAPI client
        client = TonapiClient(api_key=TONAPI_KEY, is_testnet=False)
        wallet, pub_key, priv_key, _ = WalletV5R1.from_mnemonic(client, mnemonics_list)

        bot_addr = wallet.address.to_str(is_bounceable=False)
        logging.info(f"Bot wallet (W5): {bot_addr}")

        # Check balance using TonAPI (fast and reliable)
        import aiohttp
        async with aiohttp.ClientSession() as session:
            bal_url = f"https://tonapi.io/v2/accounts/{bot_addr}"
            headers = {"Authorization": f"Bearer {TONAPI_KEY}"} if TONAPI_KEY else {}
            async with session.get(bal_url, headers=headers) as r:
                b = await r.json()
                try:
                    current_balance = int(b.get("balance", 0)) / 1e9
                except (ValueError, TypeError):
                    current_balance = 0.0
                if current_balance < amount_ton + 0.05:
                    return False, f"Недостаточно баланса на кошельке бота ({current_balance:.3f} TON)"

        # Send via tonutils
        tx_hash = await wallet.transfer(
            destination=wallet_address,
            amount=amount_ton,
            body=comment,
        )

        logging.info(f"TON sent via W5 to {wallet_address}. Amount: {amount_ton}. Tx: {tx_hash}")
        # Invalidate balance cache
        _balance_cache["timestamp"] = 0
        return True, "Успешно", tx_hash

    except Exception as e:
        import traceback
        logging.error(f"Error in send_ton_to_user (W5): {e}\n{traceback.format_exc()}")
        return False, f"Внутренняя ошибка: {str(e)}", None


async def send_stars_via_robynhood(user_id: int, stars_amount: int, recipient_username: str = None):
    """
    Отправляет Telegram Stars через RobynHood bot API.
    
    Args:
        user_id: ID пользователя-покупателя
        stars_amount: Количество звезд для отправки
        recipient_username: Username получателя (если подарок), None если себе
    
    Returns:
        tuple: (success: bool, message: str)
    """
    from .config import ROBYNHOOD_API_KEY
    
    if not ROBYNHOOD_API_KEY:
        logger.error("ROBYNHOOD_API_KEY not set in .env")
        return False, "Ошибка конфигурации API"
    
    try:
        # Определяем получателя
        recipient = recipient_username if recipient_username else user_id
        
        # RobynHood API endpoint (предполагаемый формат)
        url = "https://api.robynhood.bot/v1/stars/send"
        
        headers = {
            "Authorization": f"Bearer {ROBYNHOOD_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "recipient": recipient,
            "amount": stars_amount,
            "buyer_id": user_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    logger.info(f"Stars sent successfully: {data}")
                    return True, "Звезды успешно отправлены"
                else:
                    error_text = await r.text()
                    logger.error(f"RobynHood API error {r.status}: {error_text}")
                    return False, f"Ошибка API: {r.status}"
                    
    except Exception as e:
        logger.error(f"Error sending stars via RobynHood: {e}")
        return False, str(e)


async def send_premium_via_robynhood(user_id: int, duration_months: int, recipient_username: str = None):
    """
    Отправляет Telegram Premium через RobynHood bot API.
    """
    from .config import ROBYNHOOD_API_KEY
    
    if not ROBYNHOOD_API_KEY:
        logger.error("ROBYNHOOD_API_KEY not set in .env")
        return False, "Ошибка конфигурации API"
    
    try:
        recipient = recipient_username if recipient_username else user_id
        
        # RobynHood Premium API endpoint (предполагаемый формат)
        url = "https://api.robynhood.bot/v1/premium/send"
        
        headers = {
            "Authorization": f"Bearer {ROBYNHOOD_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "recipient": recipient,
            "duration_months": duration_months,
            "buyer_id": user_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    logger.info(f"Premium sent successfully: {data}")
                    return True, "Premium успешно отправлен"
                else:
                    error_text = await r.text()
                    logger.error(f"RobynHood API error {r.status}: {error_text}")
                    return False, f"Ошибка API: {r.status}"
                    
    except Exception as e:
        logger.error(f"Error sending premium via RobynHood: {e}")
        return False, str(e)

def calculate_service_profit(rub_amount: float, order_type: str):
    """
    Calculates the service profit for a given order.
    Considers custom markup/discount as profit.
    """
    if order_type == 'BUY':
        return rub_amount * (0.25 / 1.25)
    elif order_type == 'SELL':
        return rub_amount * (0.08 / 0.92)
    elif order_type == 'BUY_PREMIUM':
        return rub_amount * (0.20 / 1.20)
    elif order_type == 'BUY_STARS':
        # Stars: 1.38 RUB vs base cost (approx 1.15 in RobynHood)
        # For simplicity, keep it proportional to 20% if not specified otherwise
        return rub_amount * (0.23 / 1.38)
    elif order_type == 'BUY_GIFT':
        # Gift: 89 RUB fixed
        return rub_amount * (14.0 / 89.0) # Assuming approx 75 RUB cost for 80 stars
    return 0


async def notify_sales_channel(order_id: int, order: dict):
    """
    Отправляет уведомление о закрытой сделке в канал @BigStarts.
    """
    from bot import bot
    
    SALES_CHANNEL = "@BigStarts"
    
    order_type = order.get('type', 'BUY')
    rub_amount = order.get('rub_amount', 0)
    ton_amount = order.get('ton_amount', 0)
    rate = order.get('rate', 0)
    user_id = order.get('user_id', '?')
    wallet_field = order.get('user_wallet', '')
    profit = calculate_service_profit(rub_amount, order_type)
    
    # Emoji & label by type
    type_icons = {
        'BUY':        ('💎', 'Покупка TON'),
        'SELL':       ('💸', 'Продажа TON'),
        'BUY_STARS':  ('⭐', 'Покупка Звёзд'),
        'BUY_PREMIUM':('🌟', 'Покупка Premium'),
        'BUY_GIFT':   ('🎁', 'Покупка Подарка'),
    }
    icon, label = type_icons.get(order_type, ('✅', 'Заказ'))
    
    # Build extra detail line
    detail = ""
    if order_type == 'BUY':
        detail = f"🪙 TON: <b>{ton_amount} TON</b> @ {rate} ₽\n"
    elif order_type == 'SELL':
        detail = f"🪙 TON: <b>{ton_amount} TON</b> @ {rate} ₽\n"
    elif order_type == 'BUY_STARS':
        detail = f"⭐ Звёзд: <b>{int(ton_amount)}</b>\n"
    elif order_type == 'BUY_PREMIUM':
        duration = int(ton_amount)
        recipient = ''
        if '|RECIPIENT:' in wallet_field:
            r = wallet_field.split('|RECIPIENT:')[1].split('|')[0]
            if r and r != 'self': recipient = f" → @{r}"
        detail = f"🌟 Premium: <b>{duration} мес.{recipient}</b>\n"
    elif order_type == 'BUY_GIFT':
        gift_name = ''
        recipient = ''
        for p in wallet_field.split('|'):
            if p.startswith('GIFT:'): gift_name = p.split(':')[1]
            if p.startswith('RECIPIENT:'):
                r = p.split(':')[1]
                if r and r != 'self': recipient = f" → @{r}"
        detail = f"🎁 Подарок: <b>{gift_name}{recipient}</b>\n"

    msg = (
        f"{icon} <b>{label}</b> — Заказ #{order_id}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Сумма: <b>{rub_amount} ₽</b>\n"
        f"{detail}"
        f"📈 Доход: <b>+{profit:.2f} ₽</b>\n"
        f"🆔 Покупатель: <code>{user_id}</code>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"#продажа #{order_type.lower()}"
    )
    
    try:
        await bot.send_message(SALES_CHANNEL, msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send sale notification to channel: {e}")


async def process_successful_payment(order_id: int):
    """
    Handles rewards and status update after any successful payment.
    Then triggers automatic fulfillment for automated services.
    """
    from .database import update_order_status, get_order_details
    from bot import bot
    
    order = await get_order_details(order_id)
    if not order: return
    
    if order.get('status') == 'PAID': return # Avoid double processing
    
    # 1. Update status in DB
    await update_order_status(order_id, 'PAID')
    
    # 2. Notify sales channel
    await notify_sales_channel(order_id, order)
    # Referral program removed

    # 3. Trigger automatic fulfillment
    await fulfill_order(order_id)

async def verify_ton_incoming(to_address: str, amount_ton: float, comment: str) -> bool:
    """
    Checks TON blockchain for an incoming transfer to 'to_address' with exact
    amount and matching comment using TonAPI.
    """
    import aiohttp
    from .config import TONAPI_KEY
    
    nanotons = int(round(amount_ton * 1_000_000_000))
    url = f"https://tonapi.io/v2/accounts/{to_address}/events?limit=50"
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"} if TONAPI_KEY else {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=8) as r:
                if r.status != 200:
                    logger.error(f"TonAPI events fetch failed: {r.status}")
                    return False
                data = await r.json()
                events = data.get("events", [])
                for ev in events:
                    in_msg = ev.get("in_msg") or {}
                    msg_text = in_msg.get("message") or ""
                    value = in_msg.get("value")
                    if not value:
                        continue
                    if msg_text.strip() == str(comment).strip() and int(value) == nanotons:
                        return True
    except Exception as e:
        logger.error(f"TonAPI verification error: {e}")
    return False
async def fulfill_order(order_id: int):
    """
    Automatic fulfillment for Telegram Stars, Premium, and Gifts.
    Now with error tracking and DELIVERED status.
    """
    from .database import get_order_details, update_order_status, set_delivery_error
    from bot import bot
    
    order = await get_order_details(order_id)
    if not order: return
    
    # Check if already delivered
    # In database.py, update_order_status handles PAID. We'll use DELIVERED for final success.
    # If it's already DELIVERED, do nothing.
    full_order = await get_order_by_id(order_id) if 'status' not in order else order
    if full_order.get('status') == 'DELIVERED':
        logging.info(f"Order {order_id} already DELIVERED.")
        return

    user_id = order['user_id']
    order_type = order['type']
    wallet_field = order.get('user_wallet', "")

    try:
        if order_type == 'BUY':
            ton_amount = order['ton_amount']
            wallet = order.get('user_wallet')
            if not wallet:
                err = "Адрес кошелька не найден."
                await set_delivery_error(order_id, err)
                await bot.send_message(user_id, f"⚠️ Ошибка: {err} Свяжитесь с поддержкой.")
                return

            # Notify user that we are processing (or reusing existing status if triggered manually)
            status_msg = await bot.send_message(
                user_id, 
                f"⏳ <b>Подготовка к отправке {ton_amount} TON...</b>",
                parse_mode="HTML"
            )
            
            success, result_msg, tx_hash = await send_ton_to_user(wallet, ton_amount, f"Order #{order_id}")
            
            if success:
                await update_order_status(order_id, 'DELIVERED')
                await set_delivery_error(order_id, None) # Clear error if it was there
                
                explorer_url = f"https://tonviewer.com/transaction/{tx_hash}" if tx_hash else None
                success_text = (
                    f"✅ <b>Вы успешно получили {ton_amount} TON!</b>\n\n"
                    f"Средства отправлены на кошелёк:\n<code>{wallet}</code>\n"
                )
                if explorer_url:
                    success_text += f"\n🔗 <a href='{explorer_url}'>Посмотреть в Explorer</a>"
                
                await status_msg.edit_text(success_text, parse_mode="HTML", disable_web_page_preview=True)
                
                await notify_admins(
                    f"✅ <b>АВТО-ВЫПЛАТА TON УСПЕШНА!</b>\n"
                    f"Заказ: #{order_id}\n"
                    f"Сумма: {ton_amount} TON\n"
                    f"Tx: <code>{tx_hash}</code>"
                )
            else:
                await set_delivery_error(order_id, result_msg)
                logging.error(f"Fulfillment failed for order {order_id}: {result_msg}")
                
                user_err = f"⚠️ <b>Ошибка при автоматической отправке TON.</b>\n\n"
                if "balance" in result_msg.lower():
                    user_err += "В системе временно недостаточно TON. Мы отправим их вручную в ближайшее время."
                else:
                    user_err += f"Техническая заминка: <i>{result_msg}</i>\nВы можете попробовать нажать 'Проверить доставку' позже."

                from .keyboards import order_status_kb
                await status_msg.edit_text(user_err, reply_markup=order_status_kb(order_id, "PAID"), parse_mode="HTML")
                
                await notify_admins(
                    f"🚨 <b>ОШИБКА АВТО-ВЫПЛАТЫ TON!</b>\n"
                    f"Заказ: #{order_id}\n"
                    f"Ошибка: <b>{result_msg}</b>"
                )

        elif order_type in ['BUY_STARS', 'BUY_PREMIUM', 'BUY_GIFT']:
            # For these types, the logic is similar: try to send, update status on success, error on fail
            success, msg = False, "Unknown type"
            
            if order_type == 'BUY_STARS':
                recipient = None
                if "|RECIPIENT:" in wallet_field:
                    recipient = wallet_field.split("|RECIPIENT:")[1].split("|")[0]
                    if recipient == 'self': recipient = None
                success, msg = await send_stars_via_robynhood(user_id, int(order['ton_amount']), recipient)
            
            elif order_type == 'BUY_PREMIUM':
                recipient = None
                if "|RECIPIENT:" in wallet_field:
                    recipient = wallet_field.split("|RECIPIENT:")[1].split("|")[0]
                    if recipient == 'self': recipient = None
                success, msg = await send_premium_via_robynhood(user_id, int(order['ton_amount']), recipient)
            
            elif order_type == 'BUY_GIFT':
                gift_type = None
                recipient = None
                sig, anon = None, False
                parts = wallet_field.split("|")
                for p in parts:
                    if p.startswith("RECIPIENT:"): recipient = p.split(":")[1]
                    elif p.startswith("GIFT:"): gift_type = p.split(":")[1]
                    elif p.startswith("ANON:"): anon = (p.split(":")[1] == "TRUE")
                    elif p.startswith("SIGN:"): sig = p.split(":", 1)[1]
                
                from .handlers.gift_handlers import GIFTS
                gift = GIFTS.get(gift_type)
                if not gift: return

                target_id = user_id
                if recipient and recipient != 'self':
                    try:
                        chat = await bot.get_chat(f"@{recipient}")
                        target_id = chat.id
                    except:
                        from .database import get_db
                        db = await get_db()
                        async with db.execute("SELECT user_id FROM users WHERE username = ?", (recipient,)) as cur:
                            row = await cur.fetchone()
                            if row: target_id = row[0]
                
                from .userbot_manager import userbot_manager
                success, msg = await userbot_manager.send_gift(target_id, gift['id'], sig, is_anonymous=anon)

            if success:
                await update_order_status(order_id, 'DELIVERED')
                await set_delivery_error(order_id, None)
                label = "Звезды" if order_type == 'BUY_STARS' else "Premium" if order_type == 'BUY_PREMIUM' else "Подарок"
                await bot.send_message(user_id, f"✅ <b>{label} успешно доставлен!</b>", parse_mode="HTML")
            else:
                await set_delivery_error(order_id, msg)
                from .keyboards import order_status_kb
                await bot.send_message(user_id, f"⚠️ <b>Ошибка доставки:</b> {msg}", reply_markup=order_status_kb(order_id, "PAID"), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Critical error in fulfill_order: {e}")
        await set_delivery_error(order_id, str(e))

async def get_bot_ton_balance():
    """
    Возвращает баланс TON на кошельке бота с кэшированием (5 минут).
    Использует ton_utils.get_ton_balance.
    """
    from .config import TON_SENDER_WALLET
    from .ton_utils import get_ton_balance
    import time

    if not TON_SENDER_WALLET:
        return 0.0

    current_time = time.time()
    # Cache for 5 minutes (300 seconds)
    if _balance_cache["timestamp"] > 0 and (current_time - _balance_cache["timestamp"] < 300):
        return _balance_cache["balance"]

    if _balance_cache["fetching"]:
        return _balance_cache["balance"]

    _balance_cache["fetching"] = True
    try:
        balance_float = await get_ton_balance(TON_SENDER_WALLET)
        
        _balance_cache["balance"] = balance_float
        _balance_cache["timestamp"] = current_time
        return balance_float
    except Exception as e:
        logger.error(f"Error fetching TON balance: {e}")
        return _balance_cache["balance"] 
    finally:
        _balance_cache["fetching"] = False

async def notify_admins(message: str):
    """
    Отправляет уведомление всем админам из конфига.
    """
    from .config import ADMINS, TG_BOT_TOKEN
    import aiohttp
    
    if not ADMINS or not TG_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        for admin_id in ADMINS:
            payload = {
                "chat_id": admin_id,
                "text": message,
                "parse_mode": "HTML"
            }
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to notify admin {admin_id}: {resp.status}")
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id}: {e}")

async def get_robynhood_stars_balance():
    """
    Проверяет баланс звезд в RobynHood API.
    """
    from .config import ROBYNHOOD_API_KEY
    if not ROBYNHOOD_API_KEY:
        return 0
    
    # Предполагаемый эндпоинт для проверки баланса
    url = "https://api.robynhood.bot/v1/balance"
    headers = {"Authorization": f"Bearer {ROBYNHOOD_API_KEY}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("stars", 0)
                else:
                    logger.error(f"RobynHood balance check failed: {r.status}")
                    return 0
    except Exception as e:
        logger.error(f"Error checking RobynHood balance: {e}")
        return 0
