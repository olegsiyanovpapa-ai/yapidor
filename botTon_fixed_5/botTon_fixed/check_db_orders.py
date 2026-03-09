
import asyncio
import sys
import os
import aiosqlite

sys.path.append(os.getcwd())
from bot_app.config import DB_NAME

async def check_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10") as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} recent orders:")
            for row in rows:
                print(f"ID: {row['id']}, User: {row['user_id']}, Amount: {row['ton_amount']}, Status: {row['status']}, Created: {row['created_at']}")

if __name__ == "__main__":
    asyncio.run(check_orders())
