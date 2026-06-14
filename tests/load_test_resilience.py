import asyncio
import httpx
import time
import statistics

URL = "http://localhost:8000/api/health"
CONCURRENT_REQUESTS = 50
TOTAL_REQUESTS = 500

async def call_api(client, results):
    start = time.perf_counter()
    try:
        response = await client.get(URL)
        end = time.perf_counter()
        results.append(end - start)
        return response.status_code
    except Exception as e:
        results.append(None)
        return str(e)

async def main():
    print(f"🚀 Démarrage du Load Test sur {URL}...")
    print(f"   Configs: {CONCURRENT_REQUESTS} concurrents, {TOTAL_REQUESTS} requêtes au total.")
    
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        tasks = []
        for i in range(TOTAL_REQUESTS):
            tasks.append(call_api(client, results))
            if len(tasks) >= CONCURRENT_REQUESTS:
                await asyncio.gather(*tasks)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks)

    success = [r for r in results if r is not None]
    errors = len(results) - len(success)
    
    if success:
        avg = statistics.mean(success)
        p95 = statistics.quantiles(success, n=20)[18]  # 95th percentile
        print("\n📊 RÉSULTATS DU LOAD TEST :")
        print(f"   ✅ Requêtes réussies : {len(success)}")
        print(f"   ❌ Erreurs : {errors}")
        print(f"   ⏱️ Latence Moyenne : {avg:.4f}s")
        print(f"   ⏱️ Latence P95 : {p95:.4f}s")
        print(f"   📈 Débit : {len(success)/sum(success):.2f} req/s")
    else:
        print("❌ Toutes les requêtes ont échoué.")

if __name__ == "__main__":
    asyncio.run(main())
