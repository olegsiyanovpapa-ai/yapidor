
import requests
import json

address = "UQCkGQMbB2zIlclJkd7Yb3ainMarekyb9ztlscnpNQ8xZrm0"
url = f"https://toncenter.com/api/v2/getTransactions?address={address}&limit=5"

try:
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("ok"):
            print(f"Recent transactions for {address}:")
            for tx in data.get("result", []):
                val = int(tx.get("out_msgs", [{}])[0].get("value", 0)) / 1e9 if tx.get("out_msgs") else 0
                to = tx.get("out_msgs", [{}])[0].get("destination", "N/A") if tx.get("out_msgs") else "N/A"
                print(f"  Time: {tx.get('utime')}, Value: {val} TON, To: {to}")
        else:
            print(f"Error: {data}")
    else:
        print(f"HTTP Error: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
