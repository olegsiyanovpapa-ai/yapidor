
import asyncio
import sys
import os
import aiosqlite

sys.path.append(os.getcwd())
from bot_app.config import DB_NAME

async def check_users():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cur:
            rows = await cur.fetchall()
            print(f"Found {len(rows)} users:")
            for row in rows:
                print(f"ID: {row['user_id']}, Wallet: {row['default_wallet']}, Username: {row['username']}")

if __name__ == "__main__":
    asyncio.run(check_users())
