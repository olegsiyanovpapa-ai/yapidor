
"""
Gets the public key stored in the wallet contract on-chain
and compares to the mnemonic-derived public key.
"""
import asyncio
import aiohttp
from tonsdk.crypto import mnemonic_to_wallet_key

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target_addr = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

async def main():
    _pub, _priv = mnemonic_to_wallet_key(mnemonic.split())
    print(f"Mnemonic pub key: {_pub.hex()}")
    print()

    async with aiohttp.ClientSession() as session:
        # Method 1: get_public_key
        url = "https://toncenter.com/api/v2/runGetMethod"
        payload = {"address": target_addr, "method": "get_public_key", "stack": []}
        async with session.post(url, json=payload) as r:
            data = await r.json()
            if data.get("ok") and data["result"].get("stack"):
                stack = data["result"]["stack"]
                raw_num = stack[0][1]  # hex integer
                pub_int = int(raw_num, 16)
                pub_hex = f"{pub_int:064x}"
                match = " <<< MATCH!" if pub_hex == _pub.hex() else ""
                print(f"On-chain pub key (get_public_key): {pub_hex}{match}")
            else:
                print(f"get_public_key: {data}")

        # Method 2: wallet_v4 subwallet_id + seqno check
        url2 = "https://toncenter.com/api/v2/getAddressInformation"
        async with session.get(url2, params={"address": target_addr}) as r:
            info = await r.json()
            if info.get("ok"):
                r = info["result"]
                print(f"\nWallet info:")
                print(f"  Balance: {int(r.get('balance', 0)) / 1e9} TON")
                print(f"  State: {r.get('state')}")
                code_hash = r.get('code_hash', 'N/A')
                print(f"  Code hash: {code_hash}")
                
                # Known code hashes for TON wallets:
                known = {
                    "84dafa449f98a6987789ba232358072bc0f76dc4524002a5d0ce1741ad07d831": "Wallet V1R1",
                    "a0cfc2c48aee16a271f2cfc0b7382d81756cecb1017d077faaab3bb602f6868c": "Wallet V1R2",
                    "4dd3ef7f1f9174673440a01a17e699c0b45a8e1d5ea64e18b6e9c5ca3fa94f84": "Wallet V1R3",
                    "2ec38f0d9f5cf0eedab42b1cd527aee9adfb5cd4b9eb80785e6c36a2af10cc35": "Wallet V2R1",
                    "84dafa449f98a6987789ba232358072bc0f76dc4524002a5d0ce1741ad07d831": "Wallet V2R2",
                    "e3dbf7228e77f7e5b1e6d5bc52fcdb36c0cfd81b08e8bd97a4cb3b76fce68b30": "Wallet V3R1",
                    "b61041a58a7980b946e8fb9e198e3f6b5b1c8e5e1e1a4f02c3a0c6f0f8fb6b8c": "Wallet V3R2",
                }
                if code_hash in known:
                    print(f"  Wallet type: {known[code_hash]}")
                else:
                    print(f"  (code hash not matched in known list)")

asyncio.run(main())
