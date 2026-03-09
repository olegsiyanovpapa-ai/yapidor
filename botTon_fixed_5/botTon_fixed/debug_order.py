
import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from bot_app.database import init_db, create_order, get_db
from bot_app.services import get_ton_rate, get_bot_ton_balance

async def test():
    try:
        print("Initializing DB...")
        await init_db()
        
        print("Checking bot balance...")
        balance = await get_bot_ton_balance()
        print(f"Bot balance: {balance}")
        
        print("Checking TON rate...")
        rate = await get_ton_rate(False)
        print(f"TON rate: {rate}")
        
        print("Testing order creation...")
        # user_id, rub, ton, rate, wallet, expires
        order_id = await create_order(12345678, 1500, 2.0, 750.0, "0:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef", "2026-03-04T20:00:00")
        print(f"Order created with ID: {order_id}")
        
        print("Success!")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
