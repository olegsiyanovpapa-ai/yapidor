import requests
import os
import json
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PORT = int(os.getenv("PORT", 8080))
LOCAL_URL = f"http://localhost:{PORT}"
PUBLIC_URL = os.getenv("LAVA_WEBHOOK", "").replace("/lava/webhook", "")

def check_local_server():
    print(f"--- Checking Local Server (port {PORT}) ---")
    try:
        response = requests.get(f"{LOCAL_URL}/tonconnect-manifest.json", timeout=5)
        if response.status_code == 200:
            print(f"[SUCCESS] Local server is running and manifest is accessible.")
            print(f"Manifest content: {response.text[:100]}...")
            return True
        else:
            print(f"[ERROR] Local server returned status code {response.status_code}.")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Could not connect to local server at {LOCAL_URL}. Is the bot running?")
        return False

def test_lava_webhook_local():
    print(f"\n--- Testing Lava Webhook (Local) ---")
    # Simulation of Lava payload
    # sign = md5(invoice_id:amount:pay_time:secret_key_2)
    invoice_id = "test_inv_123"
    amount = "10.00"
    pay_time = "2026-03-05 22:10:00"
    order_id = "84" # example order from logs
    secret_2 = os.getenv("LAVA_SECRET_2", "")
    
    sign_str = f"{invoice_id}:{amount}:{pay_time}:{secret_2}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    
    payload = {
        "invoice_id": invoice_id,
        "amount": amount,
        "pay_time": pay_time,
        "order_id": order_id,
        "status": "success",
        "sign": sign
    }
    
    try:
        print(f"Sending mock Lava payload to {LOCAL_URL}/lava/webhook...")
        response = requests.post(f"{LOCAL_URL}/lava/webhook", json=payload, timeout=5)
        print(f"Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[ERROR] Lava local test failed: {e}")

def check_public_url():
    if not PUBLIC_URL:
        print("\n[SKIP] Public URL (LAVA_WEBHOOK) not found in .env.")
        return
    
    print(f"\n--- Checking Public URL ({PUBLIC_URL}) ---")
    try:
        manifest_url = f"{PUBLIC_URL}/tonconnect-manifest.json"
        print(f"Checking if manifest is accessible via public URL: {manifest_url}")
        response = requests.get(manifest_url, timeout=10)
        if response.status_code == 200:
            print(f"[SUCCESS] Public URL is reachable and pointing to your bot!")
        else:
            print(f"[WARNING] Public URL returned {response.status_code}. It might not be reaching your bot.")
            print("Check your Nginx config or tunnel (ngrok).")
    except Exception as e:
        print(f"[ERROR] Public URL is NOT reachable: {e}")
        print("Make sure your server is online and ports are open.")

if __name__ == "__main__":
    if check_local_server():
        test_lava_webhook_local()
    
    check_public_url()
