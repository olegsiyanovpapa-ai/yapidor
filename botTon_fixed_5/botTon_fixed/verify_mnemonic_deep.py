
"""
Tries to derive wallet from mnemonic using different approaches.
Goal: Find the derivation method that produces UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0
"""

mnemonic = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

print(f"Target: {target}")
print(f"Mnemonic words: {len(mnemonic.split())}")
print()

# Method 1: tonsdk
try:
    from tonsdk.contract.wallet import WalletV4ContractR2, WalletV3ContractR2, WalletV4ContractR1, WalletV3ContractR1
    from tonsdk.crypto import mnemonic_to_wallet_key
    
    _pub, _priv = mnemonic_to_wallet_key(mnemonic.split())
    print(f"tonsdk pub_key: {_pub.hex()}")
    
    for name, cls in [("V4R2", WalletV4ContractR2), ("V3R2", WalletV3ContractR2), ("V4R1", WalletV4ContractR1), ("V3R1", WalletV3ContractR1)]:
        w = cls(public_key=_pub, private_key=_priv, workchain=0)
        addr = w.address.to_string(True, True, False)
        match = "<<< MATCH!" if addr == target else ""
        print(f"  tonsdk {name}: {addr} {match}")
except Exception as e:
    print(f"tonsdk error: {e}")

print()

# Method 2: tonutils (if installed)
try:
    from tonutils.wallet import WalletV4R2
    from tonutils.client import TonapiClient
    
    # tonutils uses different key derivation
    from pytonapi import Tonapi
    from pytoniq_core import WalletMessage
    print("tonutils available")
except Exception as e:
    print(f"tonutils/pytoniq not available: {e}")

# Method 3: Try with PyNaCl directly using standard ed25519 from mnemonic
try:
    import hashlib
    import hmac
    from tonsdk.crypto import mnemonic_to_wallet_key

    # Some wallets use password "" (none) vs "TON default seed" 
    # tonsdk by default uses HMAC-SHA512 with "TON default seed" as key
    # Let's try with no password
    from tonsdk.crypto._mnemonic import mnemonic_to_private_key
    priv_key = mnemonic_to_private_key(mnemonic.split(), "")
    from tonsdk.contract.wallet import WalletV4ContractR2
    from nacl.signing import SigningKey
    sk = SigningKey(priv_key)
    pub_raw = bytes(sk.verify_key)
    w = WalletV4ContractR2(public_key=pub_raw, private_key=priv_key, workchain=0)
    addr = w.address.to_string(True, True, False)
    match = "<<< MATCH!" if addr == target else ""
    print(f"  tonsdk no-password approach V4R2: {addr} {match}")
except Exception as e:
    print(f"Alternative key derivation error: {e}")
