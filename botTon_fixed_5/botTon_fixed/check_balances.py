
import requests

wallets = [
    "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0", # Configured
    "UQBBN7IgcVdBZBQcXFWLxdfq0xsDr9dBONbUYOUpK82oZx0N", # From mnemonic
]

for addr in wallets:
    url = f"https://toncenter.com/api/v2/getAddressBalance?address={addr}"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                balance = int(data.get("result", 0)) / 1e9
                print(f"Address: {addr}")
                print(f"  Balance: {balance} TON")
            else:
                print(f"Address: {addr} - Error: {data}")
        else:
            print(f"Address: {addr} - HTTP Error: {resp.status_code}")
    except Exception as e:
        print(f"Address: {addr} - Error: {e}")
