
"""
The mnemonic generates keys.
We use those keys to SIGN the transaction.
We hardcode the correct wallet ADDRESS for generating the message.
This is valid because the signing key IS the wallet (deterministically).
Let's verify by using the target address as the 'bot_wallet_addr' and see if TonCenter accepts transactions from it.
"""
import asyncio
import aiohttp
from tonsdk.contract.wallet import WalletV4ContractR2
from tonsdk.crypto import mnemonic_to_wallet_key
from tonsdk.utils import bytes_to_b64str, Address

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target_addr = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"
test_send_to = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"  # Send to self for test

async def try_get_seqno(address):
    """Check what seqno the given address has on chain."""
    async with aiohttp.ClientSession() as session:
        # Check balance
        bal_url = "https://toncenter.com/api/v2/getAddressBalance"
        async with session.get(bal_url, params={"address": address}) as r:
            b = await r.json()
            balance = int(b.get("result", 0)) / 1e9
            print(f"Address: {address}")
            print(f"Balance: {balance} TON")
        
        # Check seqno
        seqno_url = "https://toncenter.com/api/v2/runGetMethod"
        async with session.post(seqno_url, json={"address": address, "method": "seqno", "stack": []}) as r:
            s = await r.json()
            if s.get("ok"):
                seqno = int(s["result"]["stack"][0][1], 16)
                print(f"Seqno: {seqno}")
            else:
                print(f"Seqno error: {s}")
                seqno = None
        return balance, seqno

async def main():
    # Get keys from mnemonic
    _pub, _priv = mnemonic_to_wallet_key(mnemonic.split())
    print(f"Pub key from mnemonic: {_pub.hex()}")
    
    # Use WalletV4ContractR2 but with the TARGET address for signing
    wallet = WalletV4ContractR2(public_key=_pub, private_key=_priv, workchain=0)
    generated_addr = wallet.address.to_string(True, True, False)
    print(f"Generated address: {generated_addr}")
    print(f"Target address:    {target_addr}")
    print(f"Match: {generated_addr == target_addr}\n")
    
    # Check BOTH addresses
    print("=== Generated address on-chain ===")
    bal1, seq1 = await try_get_seqno(generated_addr)
    print()
    print("=== Target address on-chain ===")
    bal2, seq2 = await try_get_seqno(target_addr)

asyncio.run(main())
