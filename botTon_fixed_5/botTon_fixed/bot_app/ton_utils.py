"""
Утилиты для работы с TON Payment Links и Tonkeeper
"""
from urllib.parse import urlencode
import base64

def crc16(data: bytes) -> bytes:
    """Вычисляет стандартный CRC16 (CCITT) для TON адреса"""
    reg = 0
    poly = 0x1021
    for byte in data:
        reg ^= (byte << 8)
        for _ in range(8):
            if reg & 0x8000:
                reg = (reg << 1) ^ poly
            else:
                reg = (reg << 1)
            reg &= 0xFFFF
    return reg.to_bytes(2, 'big')

def raw_to_user_friendly(raw_address: str, bounceable: bool = False) -> str:
    """
    Конвертирует сырой адрес (0:...) в пользовательский формат (Base64)
    
    Args:
        raw_address: Адрес в формате workchain:hash
        bounceable: True для bounceable адреса (EQ...), False для non-bounceable (UQ...)
        
    Returns:
        Адрес в формате Base64URL
    """
    if not raw_address or ":" not in raw_address:
        return raw_address
    
    try:
        workchain, hash_hex = raw_address.split(":")
        workchain = int(workchain)
        hash_bytes = bytes.fromhex(hash_hex)
        
        # Флаги: 0x11 - bounceable, 0x51 - non-bounceable
        tag = 0x11 if bounceable else 0x51
        
        # Байт воркчейна
        wc_byte = workchain & 0xFF
        
        data = bytes([tag, wc_byte]) + hash_bytes
        crc = crc16(data)
        
        full_data = data + crc
        return base64.urlsafe_b64encode(full_data).decode('utf-8')
    except Exception:
        return raw_address

def generate_ton_payment_link(address: str, amount_ton: float, comment: str = "") -> str:
    """
    Генерирует TON Payment Link для открытия в Tonkeeper
    
    Args:
        address: TON адрес получателя (EQ... или UQ...)
        amount_ton: Сумма в TON
        comment: Комментарий к платежу (например, номер заказа)
    
    Returns:
        Ссылка формата ton://transfer/ADDRESS?amount=X&text=COMMENT
    """
    # TON использует nanotons (1 TON = 1_000_000_000 nanotons)
    amount_nanoton = int(round(amount_ton * 1_000_000_000))
    
    params = {
        "amount": str(amount_nanoton),
    }
    
    if comment:
        params["text"] = str(comment)
    
    query_string = urlencode(params)
    # Native TON protocol is often more reliable inside apps
    return f"ton://transfer/{address}?{query_string}"


def generate_tonkeeper_connect_link(return_url: str = "https://t.me/YourBotUsername") -> str:
    """
    Генерирует deeplink для подключения кошелька Tonkeeper
    (упрощенная версия без TON Connect)
    
    Args:
        return_url: URL для возврата после подключения
    
    Returns:
        Deeplink для Tonkeeper
    """
    # Упрощенная версия - просто открывает Tonkeeper
    # Для полноценного TON Connect нужен манифест и webhook
    return "https://tonkeeper.com/"


def validate_ton_address(address: str) -> bool:
    """
    Базовая валидация TON адреса
    
    Args:
        address: TON адрес для проверки
    
    Returns:
        True если адрес валиден
    """
    if not address:
        return False
    
    # Базовая проверка формата
    if not (address.startswith("EQ") or address.startswith("UQ")):
        return False
    
    # Проверка длины (48 символов base64)
    if len(address) != 48:
        return False
    
    return True


def format_ton_amount(nanotons: int) -> float:
    """
    Конвертирует nanotons в TON
    
    Args:
        nanotons: Количество nanotons
    
    Returns:
        Количество TON
    """
    return nanotons / 1_000_000_000


def generate_qr_code_image(data: str):
    """
    Генерирует QR код из строки
    
    Args:
        data: Данные для QR кода (URL, адрес и т.д.)
    
    Returns:
        BytesIO объект с PNG изображением
    """
    import qrcode
    from io import BytesIO
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    return bio


async def get_ton_balance(wallet_address: str) -> float:
    """
    Получает баланс TON кошелька
    
    Args:
        wallet_address: Адрес TON кошелька
    
    Returns:
        Баланс в TON
    """
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # Используем публичный API TON
            url = f"https://toncenter.com/api/v2/getAddressBalance?address={wallet_address}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        # Конвертируем nanotons в TON
                        balance_nanoton = int(data.get("result", 0))
                        return balance_nanoton / 1_000_000_000
    except Exception as e:
        import logging
        logging.error(f"Error fetching TON balance: {e}")
    
    return 0.0


async def get_usdt_balance(wallet_address: str) -> float:
    """
    Получает баланс USDT (jUSDT) на TON кошельке
    
    Args:
        wallet_address: Адрес TON кошелька
    
    Returns:
        Баланс в USDT
    """
    import aiohttp
    
    try:
        # jUSDT jetton master address на TON
        JUSDT_MASTER = "EQBynBO23ywHy_CgarY9NK9FTz0yDsG82PtcbSTQgGoXwiuA"
        
        async with aiohttp.ClientSession() as session:
            # Получаем jetton wallet адрес для данного кошелька
            url = f"https://toncenter.com/api/v2/runGetMethod"
            params = {
                "address": JUSDT_MASTER,
                "method": "get_wallet_address",
                "stack": f'[["tvm.Slice","{wallet_address}"]]'
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        # Получаем баланс jetton wallet
                        jetton_wallet = data.get("result", {}).get("stack", [[]])[0]
                        if jetton_wallet:
                            balance_url = f"https://toncenter.com/api/v2/runGetMethod"
                            balance_params = {
                                "address": jetton_wallet,
                                "method": "get_wallet_data"
                            }
                            async with session.get(balance_url, params=balance_params) as balance_response:
                                if balance_response.status == 200:
                                    balance_data = await balance_response.json()
                                    if balance_data.get("ok"):
                                        stack = balance_data.get("result", {}).get("stack", [])
                                        if stack and len(stack) > 0:
                                            balance = int(stack[0].get("value", "0"))
                                            # USDT имеет 6 десятичных знаков
                                            return balance / 1_000_000
    except Exception as e:
        import logging
        logging.error(f"Error fetching USDT balance: {e}")
    
    return 0.0
