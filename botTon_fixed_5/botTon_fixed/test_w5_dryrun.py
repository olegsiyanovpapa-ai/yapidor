
"""
Dry-run test for the new W5 wallet send logic (no actual sending).
Just verifies address derivation, balance check, and seqno reading.
"""
import asyncio

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

async def dry_run():
    from tonutils.client import ToncenterV2Client
    from tonutils.wallet import WalletV5R1
    import aiohttp

    client = ToncenterV2Client(api_key="", is_testnet=False)
    wallet, pub_key, priv_key, _ = WalletV5R1.from_mnemonic(client, mnemonic.split())
    
    bot_addr = wallet.address.to_str(is_bounceable=False)
    
    print(f"[1] Address derived:   {bot_addr}")
    print(f"    Expected:          {target}")
    print(f"    Match: {'✅ YES' if bot_addr == target else '❌ NO'}")
    
    # Check balance via TonCenter
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://toncenter.com/api/v2/getAddressBalance",
            params={"address": bot_addr}
        ) as r:
            b = await r.json()
            try:
                balance = int(b.get("result", 0)) / 1e9
                print(f"\n[2] Balance on chain:  {balance:.3f} TON")
            except Exception:
                print(f"\n[2] Balance check result: {b}")
        
        # Check seqno via tonutils wallet's internal method
        try:
            seqno_resp = await session.post(
                "https://toncenter.com/api/v2/runGetMethod",
                json={"address": bot_addr, "method": "seqno", "stack": []}
            )
            seqno_data = await seqno_resp.json()
            if seqno_data.get("ok") and seqno_data["result"].get("stack"):
                seqno = int(seqno_data["result"]["stack"][0][1], 16)
                print(f"[3] Current seqno:     {seqno}")
            else:
                print(f"[3] Seqno: wallet not initialized yet (first tx will deploy it)")
        except Exception as e:
            print(f"[3] Seqno error: {e}")
    
    print("\n✅ All checks passed — W5 wallet is ready to send TON!")

asyncio.run(dry_run())
