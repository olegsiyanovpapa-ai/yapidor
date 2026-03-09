
import asyncio
import sys
import os
import aiosqlite

sys.path.append(os.getcwd())
from bot_app.config import DB_NAME

async def check_sessions():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM ton_connect_sessions") as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} sessions:")
            for row in rows:
                print(f"ID: {row['user_id']}, Address: {row['wallet_address']}")

if __name__ == "__main__":
    asyncio.run(check_sessions())
