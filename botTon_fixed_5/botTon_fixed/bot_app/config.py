import os
from dotenv import load_dotenv

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
SALE_ADMINS = [8132138841, 1326184152]
DB_NAME = "db.sqlite"

TON_SENDER_WALLET = os.getenv("TON_SENDER_WALLET")
TON_SENDER_MNEMONIC = os.getenv("TON_SENDER_MNEMONIC")
TONAPI_KEY = os.getenv("TONAPI_KEY", "")

# Lava.ru
LAVA_PROJECT_ID = os.getenv("LAVA_PROJECT_ID")
LAVA_API_KEY = os.getenv("LAVA_API_KEY")
LAVA_SECRET_1 = os.getenv("LAVA_SECRET_1")
LAVA_SECRET_2 = os.getenv("LAVA_SECRET_2")
LAVA_WEBHOOK = os.getenv("LAVA_WEBHOOK")
LAVA_SUCCESS_URL = os.getenv("LAVA_SUCCESS_URL")
LAVA_FAIL_URL = os.getenv("LAVA_FAIL_URL")

# TON Markup logic: Buy +25%, Sell -8%
ORDER_LIFETIME = 15

# TON Connect
TON_CONNECT_MANIFEST_URL = os.getenv("TON_CONNECT_MANIFEST_URL", "https://ton.villavpn.ru/tonconnect-manifest.json")
TON_CONNECT_TIMEOUT = int(os.getenv("TON_CONNECT_TIMEOUT", "300"))  # 5 minutes

# RobynHood Bot API
ROBYNHOOD_API_KEY = os.getenv("ROBYNHOOD_API_KEY")

# UserBot
USERBOT_API_ID = os.getenv("USERBOT_API_ID")
USERBOT_API_HASH = os.getenv("USERBOT_API_HASH")
USERBOT_SESSION_NAME = "userbot_session"

