
"""
Test BIP39 standard derivation for TON wallets.
Some apps (e.g. old Tonkeeper) use standard BIP39 + m/44'/607'/0'/0'/0'
"""
import hashlib
import hmac
import struct

mnemonic_phrase = "REDACTED_BY_ANTIGRAVITY"
target = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

# --- Method: BIP39 -> BIP32 -> Ed25519 ---
# Standard BIP39 seed derivation (PBKDF2 HMAC-SHA512)
def bip39_to_seed(mnemonic, passphrase=""):
    mnemonic_bytes = mnemonic.encode('utf-8')
    salt = ("mnemonic" + passphrase).encode('utf-8')
    return hashlib.pbkdf2_hmac('sha512', mnemonic_bytes, salt, 2048)

def derive_ed25519_key(seed, path="m/44'/607'/0'/0'/0'"):
    """SLIP-0010 Ed25519 derivation"""
    def hmac_sha512(key, data):
        return hmac.new(key, data, hashlib.sha512).digest()
    
    # Master key
    I = hmac_sha512(b"ed25519 seed", seed)
    key, chain_code = I[:32], I[32:]
    
    # Parse path
    segments = path.lstrip('m/').split('/')
    for seg in segments:
        hardened = seg.endswith("'")
        index = int(seg.rstrip("'"))
        if hardened:
            index += 0x80000000
        data = b'\x00' + key + struct.pack('>I', index)
        I = hmac_sha512(chain_code, data)
        key, chain_code = I[:32], I[32:]
    
    return key

def ed25519_pub_from_priv(priv_bytes):
    try:
        from nacl.signing import SigningKey
        return bytes(SigningKey(priv_bytes).verify_key)
    except:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pynacl", "-q"])
        from nacl.signing import SigningKey
        return bytes(SigningKey(priv_bytes).verify_key)

seed = bip39_to_seed(mnemonic_phrase)
print(f"BIP39 seed (hex): {seed.hex()[:32]}...")

# Try multiple derivation paths
paths = [
    "m/44'/607'/0'/0'/0'",
    "m/44'/607'/0'",
    "m/44'/607'/0'/0'",
]

for path in paths:
    try:
        priv = derive_ed25519_key(seed, path)
        pub = ed25519_pub_from_priv(priv)
        print(f"  Path {path}")
        print(f"    priv: {priv.hex()}")
        print(f"    pub:  {pub.hex()}")
        
        # Now build TON wallet address from pub key
        from tonsdk.contract.wallet import WalletV4ContractR2, WalletV3ContractR2
        for name, cls in [("V4R2", WalletV4ContractR2), ("V3R2", WalletV3ContractR2)]:
            w = cls(public_key=pub, private_key=priv, workchain=0)
            addr = w.address.to_string(True, True, False)
            match = " <<< MATCH!" if addr == target else ""
            print(f"    {name}: {addr}{match}")
    except Exception as e:
        print(f"  Path {path} error: {e}")
