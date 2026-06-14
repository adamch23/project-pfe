import requests
import json

url = "http://localhost:8000/api/login"
payload = {
    "email": "adam2003y@gmail.com",
    "password": "AdminSecure2026!"
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
