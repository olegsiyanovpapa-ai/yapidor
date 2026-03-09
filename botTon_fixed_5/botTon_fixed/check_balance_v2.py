
import asyncio
import os
from dotenv import load_dotenv
import aiohttp

async def check_balance():
    load_dotenv()
    address = os.getenv("TON_SENDER_WALLET")
    tonapi_key = os.getenv("TONAPI_KEY")

    if not address:
        print("TON_SENDER_WALLET not found in .env")
        return

    try:
        async with aiohttp.ClientSession() as session:
            bal_url = f"https://tonapi.io/v2/accounts/{address}"
            headers = {"Authorization": f"Bearer {tonapi_key}"} if tonapi_key else {}
            async with session.get(bal_url, headers=headers) as r:
                if r.status == 200:
                    b = await r.json()
                    balance = int(b.get("balance", 0)) / 1e9
                    print(f"Address: {address}")
                    print(f"Current Balance: {balance} TON")
                else:
                    print(f"Failed to fetch balance: {r.status}")
                    print(await r.text())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_balance())
