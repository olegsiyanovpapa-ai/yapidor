
import asyncio

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

async def test():
    try:
        from tonutils.wallet import WalletV5R1
        from tonutils.client import ToncenterClient
        
        client = ToncenterClient(api_key="")  # no key needed for address test
        wallet, pub, priv, mnem = WalletV5R1.from_mnemonic(client, mnemonic.split())
        addr = wallet.address.to_str(is_bounceable=False)
        match = " <<< MATCH!" if addr == target else ""
        print(f"tonutils WalletV5R1 (non-bounceable): {addr}{match}")
        addr2 = wallet.address.to_str(is_bounceable=True)
        print(f"tonutils WalletV5R1 (bounceable):     {addr2}")
        print(f"Target:                                {target}")
        print(f"Pub key: {pub.hex()}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()

asyncio.run(test())
