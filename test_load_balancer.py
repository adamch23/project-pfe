import httpx
import time
from collections import Counter

def test_load_balancer(url="http://localhost/api/health", iterations=10):
    print(f"Testing Load Balancer at {url}...")
    container_ids = []
    
    for i in range(iterations):
        try:
            response = httpx.get(url, timeout=5)
            if response.status_code == 200:
                cid = response.json().get("container_id", "unknown")
                container_ids.append(cid)
                print(f"Request {i+1}: Hosted by {cid}")
            else:
                print(f"Request {i+1}: Failed with status {response.status_code}")
        except Exception as e:
            print(f"Request {i+1}: Error: {e}")
        time.sleep(0.5)

    counts = Counter(container_ids)
    print("\nResults:")
    for cid, count in counts.items():
        print(f"Container {cid}: {count} requests")
    
    if len(counts) > 1:
        print("\nSUCCESS: Load balancing verified (multiple containers responded).")
    else:
        print("\nWARNING: Only one container responded. Check if multiple replicas are running.")

if __name__ == "__main__":
    test_load_balancer()
