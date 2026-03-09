
import asyncio
import os
from dotenv import load_dotenv
from tonutils.client import TonapiClient
from tonutils.wallet import WalletV5R1

async def verify_wallet():
    load_dotenv()
    mnemonic = os.getenv("TON_SENDER_MNEMONIC")
    expected_address = os.getenv("TON_SENDER_WALLET")
    tonapi_key = os.getenv("TONAPI_KEY")

    if not mnemonic:
        print("❌ TON_SENDER_MNEMONIC not found in .env")
        return

    try:
        client = TonapiClient(api_key=tonapi_key, is_testnet=False)
        mnemonics_list = mnemonic.strip().split()
        wallet, pub_key, priv_key, _ = WalletV5R1.from_mnemonic(client, mnemonics_list)
        
        actual_address = wallet.address.to_str(is_bounceable=False)
        print(f"Mnemonic Address (actual): {actual_address}")
        print(f"Expected Address (.env):  {expected_address}")
        
        if actual_address == expected_address:
            print("✅ Wallet addresses match!")
        else:
            print("❌ Wallet addresses DO NOT match!")
            
        # Check balance
        import aiohttp
        async with aiohttp.ClientSession() as session:
            bal_url = f"https://tonapi.io/v2/accounts/{actual_address}"
            headers = {"Authorization": f"Bearer {tonapi_key}"} if tonapi_key else {}
            async with session.get(bal_url, headers=headers) as r:
                if r.status == 200:
                    b = await r.json()
                    balance = int(b.get("balance", 0)) / 1e9
                    print(f"Current Balance: {balance} TON")
                else:
                    print(f"❌ Failed to fetch balance: {r.status}")
    except Exception as e:
        print(f"❌ Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify_wallet())
