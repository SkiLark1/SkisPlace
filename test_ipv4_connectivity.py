import requests
import sys

API_URL = "http://127.0.0.1:8000/api/v1"

def check_ping():
    try:
        print(f"Checking {API_URL}/public/ping ...")
        resp = requests.get(f"{API_URL}/public/ping", timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 401 or resp.status_code == 200:
            print("Success")
            return True
        return False
    except Exception as e:
        print(f"Error checking ping: {e}")
        return False

if __name__ == "__main__":
    if check_ping():
        sys.exit(0)
    else:
        sys.exit(1)
