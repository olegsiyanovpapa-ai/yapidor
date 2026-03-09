import asyncio
import sys
import os

# Add the project directory to sys.path to import bot_app
sys.path.append(os.getcwd())

from bot_app.services import get_premium_prices_rub, fetch_fragment_premium_prices

async def test_pricing():
    print("--- Testing Fragment Scraping ---")
    ton_prices = await fetch_fragment_premium_prices()
    if ton_prices:
        print(f"Prices in TON from Fragment: {ton_prices}")
    else:
        print("Failed to fetch prices from Fragment. Check XPaths or internet connection.")
    
    print("\n--- Testing RUB Calculation ---")
    rub_prices = await get_premium_prices_rub()
    print(f"Final RUB prices with markup: {rub_prices}")

if __name__ == "__main__":
    asyncio.run(test_pricing())
