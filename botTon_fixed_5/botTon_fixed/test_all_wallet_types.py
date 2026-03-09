
"""
Try all available wallet classes in tonsdk to match the target address.
Also investigate raw address format differences.
"""
mnemonic = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

from tonsdk.crypto import mnemonic_to_wallet_key
import tonsdk.contract.wallet as wallet_module
import inspect

_pub, _priv = mnemonic_to_wallet_key(mnemonic.split())
print(f"pub_key: {_pub.hex()}")
print(f"Target:  {target}\n")

# Get all wallet classes available in tonsdk
classes = [(name, cls) for name, cls in inspect.getmembers(wallet_module, inspect.isclass) if 'Wallet' in name or 'Contract' in name]

for name, cls in classes:
    try:
        for wc in [0, -1]:
            try:
                w = cls(public_key=_pub, private_key=_priv, workchain=wc)
                if not hasattr(w, 'address'):
                    continue
                addr = w.address.to_string(True, True, False)
                match = " <<< MATCH!" if addr == target else ""
                if match:
                    print(f"  {name} workchain={wc}: {addr}{match}")
            except Exception:
                pass
    except Exception:
        pass

print("Scan complete.")

# Also: show the raw hash of the target to help identify
from tonsdk.utils import Address
a = Address(target)
print(f"\nTarget raw: {a.hash_part.hex()}")
print(f"Target workchain: {a.wc}")
# UQCkGQ... -> what pub key does this correspond to?
