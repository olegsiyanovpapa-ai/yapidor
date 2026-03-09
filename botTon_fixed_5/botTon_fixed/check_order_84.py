
import asyncio
import sys
import os
import aiosqlite

sys.path.append(os.getcwd())
from bot_app.config import DB_NAME

async def check_order_84():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = 84") as cur:
            row = await cur.fetchone()
            if row:
                print(f"Order #84 details:")
                for key in row.keys():
                    print(f"  {key}: {row[key]}")
            else:
                print("Order #84 not found in database.")

if __name__ == "__main__":
    asyncio.run(check_order_84())
