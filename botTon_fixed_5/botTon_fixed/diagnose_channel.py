import asyncio
from dotenv import load_dotenv
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
TOKEN = os.getenv("TG_BOT_TOKEN")

import aiohttp

LINKED_GROUP_ID = -1003128763377

async def main():
    async with aiohttp.ClientSession() as session:
        # Get bot info
        async with session.get(f"https://api.telegram.org/bot{TOKEN}/getMe") as r:
            me = (await r.json())["result"]
            print(f"Bot: @{me['username']} (id={me['id']})")
            print(f"  can_read_all_group_messages: {me.get('can_read_all_group_messages')}")
        
        # Get bot status in linked group
        async with session.get(
            f"https://api.telegram.org/bot{TOKEN}/getChatMember",
            params={"chat_id": LINKED_GROUP_ID, "user_id": me["id"]}
        ) as r:
            result = await r.json()
            if result.get("ok"):
                member = result["result"]
                print(f"\nBot status in linked group ({LINKED_GROUP_ID}):")
                print(f"  status: {member['status']}")
                print(f"  can_send_messages: {member.get('can_send_messages', 'N/A')}")
                print(f"  can_read_messages: {member.get('can_read_messages', 'N/A')}")
            else:
                print(f"\nERROR getting bot status in group: {result}")
                print(">>> BOT IS NOT IN THE GROUP OR GROUP IS PRIVATE!")
        
        # Try to get group info
        async with session.get(
            f"https://api.telegram.org/bot{TOKEN}/getChat",
            params={"chat_id": LINKED_GROUP_ID}
        ) as r:
            result = await r.json()
            if result.get("ok"):
                chat = result["result"]
                print(f"\nGroup info:")
                print(f"  title: {chat.get('title')}")
                print(f"  type: {chat.get('type')}")
                print(f"  username: {chat.get('username', 'no username')}")
            else:
                print(f"\nERROR getting group info: {result.get('description')}")

asyncio.run(main())
