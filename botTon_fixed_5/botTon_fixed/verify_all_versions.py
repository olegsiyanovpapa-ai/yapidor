
from tonsdk.contract.wallet import Wallets, WalletV4ContractR2, WalletV3ContractR1, WalletV3ContractR2, WalletV4ContractR1
from tonsdk.crypto import mnemonic_to_wallet_key
import sys

mnemonic = "REDACTED_BY_ANTIGRAVITY"
expected_addr = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"

def verify_wallet():
    mnemonics_list = mnemonic.split(" ")
    _pub_key, priv_key = mnemonic_to_wallet_key(mnemonics_list)
    
    versions = {
        "V4R2": WalletV4ContractR2,
        "V3R1": WalletV3ContractR1,
        "V3R2": WalletV3ContractR2,
        "V4R1": WalletV4ContractR1,
    }
    
    for name, v_class in versions.items():
        wallet = v_class(public_key=_pub_key, private_key=priv_key, workchain=0)
        addr = wallet.address.to_string(True, True, False)
        print(f"{name} Address: {addr}")
        if addr == expected_addr:
            print(f"!!! MATCH FOUND for {name} !!!")
            return
            
    print("NO MATCH FOUND among tested versions.")

if __name__ == "__main__":
    verify_wallet()
