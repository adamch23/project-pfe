import httpx
import time

URL_HEALTH = "http://localhost/api/health"
URL_FAIL = "http://localhost/api/chaos/fail"
URL_RECOVER = "http://localhost/api/chaos/recover"

def check_status():
    try:
        resp = httpx.get(URL_HEALTH, timeout=2)
        return resp.status_code, resp.json().get("container_id")
    except Exception as e:
        return 500, str(e)

def test_resilience():
    print("--- 1. Initial State ---")
    status, cid = check_status()
    print(f"Status: {status}, Container: {cid}")

    print("\n--- 2. Inducing failure on one instance ---")
    # This will hit whichever instance the LB chooses
    try:
        resp = httpx.get(URL_FAIL)
        failed_cid = resp.json().get("message", "").split("(")[-1].strip(")") # Just for logging
        print(f"Failure command sent. One instance should теперь return 503.")
    except:
        print("Failed to send chaos command")

    print("\n--- 3. Testing Resilience (LB should bypass or show 503 then retry) ---")
    print("Nginx is configured with max_fails=3. We might see some errors before it stabilizes.")
    
    results = []
    for i in range(10):
        status, cid = check_status()
        results.append(status)
        print(f"Check {i+1}: Status {status} from {cid}")
        time.sleep(1)

    success_rate = results.count(200) / len(results) * 100
    print(f"\nSuccess Rate during partial failure: {success_rate}%")
    
    if success_rate > 50:
        print("RESILIENCE OK: Load balancer is likely bypassing the failed node.")
    else:
        print("RESILIENCE WEAK: Failed node is still being served frequently.")

    print("\n--- 4. Recovering ---")
    httpx.get(URL_RECOVER)
    print("Recovery command sent.")

if __name__ == "__main__":
    test_resilience()
