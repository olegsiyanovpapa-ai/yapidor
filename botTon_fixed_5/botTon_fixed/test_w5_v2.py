
import asyncio

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

async def test():
    from tonutils.client import ToncenterV2Client
    from tonutils.wallet import WalletV5R1
    
    client = ToncenterV2Client(api_key="", is_testnet=False)
    wallet, pub, priv, _ = WalletV5R1.from_mnemonic(client, mnemonic.split())
    
    addr_nb = wallet.address.to_str(is_bounceable=False)
    addr_b  = wallet.address.to_str(is_bounceable=True)
    
    print(f"WalletV5R1 non-bounceable: {addr_nb}")
    print(f"WalletV5R1 bounceable:     {addr_b}")
    print(f"Target:                    {target}")
    
    match_nb = addr_nb == target
    match_b  = addr_b  == target
    print(f"Match non-bounceable: {match_nb}, Match bounceable: {match_b}")
    
    if not match_nb and not match_b:
        # Maybe it's a different address format - try raw
        print(f"\nRaw address: {wallet.address.to_str(is_bounceable=False, is_url_safe=True)}")

asyncio.run(test())
