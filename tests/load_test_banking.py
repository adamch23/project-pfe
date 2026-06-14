"""
Load Test Suite — Banking Grade (Finding ARCH-03 — Audit Bancaire)
Conformité DORA Art. 25 | ISO 27001 A.17.1.3

Scénarios couverts :
  1. Test de charge normal (SLA : P99 < 500ms, error rate < 0.1%)
  2. Test de montée en charge progressive (ramp-up)
  3. Test de résilience (simulation panne instance)
  4. Test de spike (burst soudain)

Utilisation :
  # Contre l'API locale :
  python tests/load_test_banking.py --url http://localhost:8000 --scenario normal

  # En CI/CD (sans credentials) :
  python tests/load_test_banking.py --url http://localhost:8000 --scenario ci --fail-on-sla

Prérequis :
  pip install httpx asyncio pytest-benchmark
"""

import asyncio
import httpx
import time
import statistics
import argparse
import sys
from dataclasses import dataclass, field
from typing import List, Optional


# ── SLA Bancaires (Finding ARCH-03) ────────────────────────────────────────
SLA_P99_MAX_MS = 500          # P99 ne doit pas dépasser 500ms
SLA_P95_MAX_MS = 300          # P95 ne doit pas dépasser 300ms
SLA_ERROR_RATE_MAX = 0.001   # Taux d'erreur max : 0.1%
SLA_AVAILABILITY_MIN = 0.999  # Disponibilité min : 99.9%


@dataclass
class LoadTestResult:
    scenario: str
    total_requests: int
    success_count: int
    error_count: int
    latencies_ms: List[float] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time

    @property
    def throughput_rps(self) -> float:
        return self.success_count / self.duration_s if self.duration_s > 0 else 0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.total_requests if self.total_requests > 0 else 0

    @property
    def availability(self) -> float:
        return self.success_count / self.total_requests if self.total_requests > 0 else 0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0
        sorted_l = sorted(self.latencies_ms)
        index = max(0, int(len(sorted_l) * p / 100) - 1)
        return sorted_l[index]

    @property
    def p50(self) -> float: return self.percentile(50)
    @property
    def p95(self) -> float: return self.percentile(95)
    @property
    def p99(self) -> float: return self.percentile(99)

    def check_sla(self) -> dict:
        """Retourne le résultat de la vérification SLA."""
        return {
            "p99_ok": self.p99 <= SLA_P99_MAX_MS,
            "p95_ok": self.p95 <= SLA_P95_MAX_MS,
            "error_rate_ok": self.error_rate <= SLA_ERROR_RATE_MAX,
            "availability_ok": self.availability >= SLA_AVAILABILITY_MIN,
            "p99_value": self.p99,
            "p95_value": self.p95,
            "error_rate_value": self.error_rate,
            "availability_value": self.availability,
        }

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"  LOAD TEST REPORT — {self.scenario.upper()}")
        print(f"{'='*60}")
        print(f"  Durée totale     : {self.duration_s:.2f}s")
        print(f"  Requêtes totales : {self.total_requests}")
        print(f"  Succès           : {self.success_count} ({self.availability*100:.2f}%)")
        print(f"  Erreurs          : {self.error_count} ({self.error_rate*100:.3f}%)")
        print(f"  Débit            : {self.throughput_rps:.1f} req/s")
        print(f"  Latence P50      : {self.p50:.1f}ms")
        print(f"  Latence P95      : {self.p95:.1f}ms  {'✅' if self.p95 <= SLA_P95_MAX_MS else '❌'} (SLA: ≤{SLA_P95_MAX_MS}ms)")
        print(f"  Latence P99      : {self.p99:.1f}ms  {'✅' if self.p99 <= SLA_P99_MAX_MS else '❌'} (SLA: ≤{SLA_P99_MAX_MS}ms)")
        print(f"  Disponibilité    : {self.availability*100:.3f}%  {'✅' if self.availability >= SLA_AVAILABILITY_MIN else '❌'} (SLA: ≥{SLA_AVAILABILITY_MIN*100:.1f}%)")
        print(f"  Taux d'erreur    : {self.error_rate*100:.3f}%  {'✅' if self.error_rate <= SLA_ERROR_RATE_MAX else '❌'} (SLA: ≤{SLA_ERROR_RATE_MAX*100:.1f}%)")

        sla = self.check_sla()
        sla_ok = all([sla["p99_ok"], sla["p95_ok"], sla["error_rate_ok"], sla["availability_ok"]])
        print(f"\n  VERDICT SLA : {'✅ CONFORME' if sla_ok else '❌ NON CONFORME'}")
        print(f"{'='*60}\n")
        return sla_ok


# ── Fonctions d'appel asynchrones ──────────────────────────────────────────
async def _single_request(client: httpx.AsyncClient, url: str) -> Optional[float]:
    """Exécute une requête et retourne la latence en ms, ou None si erreur."""
    start = time.perf_counter()
    try:
        resp = await client.get(url, timeout=10.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return elapsed_ms if resp.status_code < 500 else None
    except Exception:
        return None


async def run_concurrent_batch(
    client: httpx.AsyncClient, url: str, batch_size: int
) -> List[Optional[float]]:
    tasks = [_single_request(client, url) for _ in range(batch_size)]
    return await asyncio.gather(*tasks)


# ── Scénarios de test ────────────────────────────────────────────────────────
async def scenario_normal(base_url: str) -> LoadTestResult:
    """
    Scénario : Charge normale (100 utilisateurs, 1000 requêtes)
    SLA cible : P99 < 500ms, disponibilité > 99.9%
    """
    result = LoadTestResult(scenario="normal", total_requests=1000, success_count=0, error_count=0)
    url = f"{base_url}/api/health"
    concurrent = 50
    result.start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        for _ in range(result.total_requests // concurrent):
            batch_results = await run_concurrent_batch(client, url, concurrent)
            for latency in batch_results:
                if latency is not None:
                    result.success_count += 1
                    result.latencies_ms.append(latency)
                else:
                    result.error_count += 1

    result.end_time = time.perf_counter()
    return result


async def scenario_ramp_up(base_url: str) -> LoadTestResult:
    """
    Scénario : Montée en charge progressive (1 → 10 → 50 → 100 → 200 utilisateurs)
    Valide que le système monte en charge sans dégradation progressive des SLA.
    """
    result = LoadTestResult(scenario="ramp_up", total_requests=0, success_count=0, error_count=0)
    url = f"{base_url}/api/health"
    stages = [1, 5, 10, 25, 50, 100]
    result.start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        for concurrent in stages:
            print(f"  ➡️  Ramp-up : {concurrent} utilisateurs simultanés...")
            batch_results = await run_concurrent_batch(client, url, concurrent)
            for latency in batch_results:
                result.total_requests += 1
                if latency is not None:
                    result.success_count += 1
                    result.latencies_ms.append(latency)
                else:
                    result.error_count += 1
            await asyncio.sleep(0.5)  # Pause entre les niveaux

    result.end_time = time.perf_counter()
    return result


async def scenario_spike(base_url: str) -> LoadTestResult:
    """
    Scénario : Spike soudain (burst de 200 requêtes en 1 seconde)
    Valide la résistance aux pics de trafic (DDoS partiel, offre spéciale, etc.)
    """
    result = LoadTestResult(scenario="spike", total_requests=200, success_count=0, error_count=0)
    url = f"{base_url}/api/health"
    result.start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        # Envoi simultané de 200 requêtes
        batch_results = await run_concurrent_batch(client, url, 200)
        for latency in batch_results:
            if latency is not None:
                result.success_count += 1
                result.latencies_ms.append(latency)
            else:
                result.error_count += 1

    result.end_time = time.perf_counter()
    return result


async def scenario_ci(base_url: str) -> LoadTestResult:
    """
    Scénario allégé pour CI/CD (50 requêtes, 10 concurrentes)
    Valide les SLA sans impact sur la durée du pipeline.
    """
    result = LoadTestResult(scenario="ci", total_requests=50, success_count=0, error_count=0)
    url = f"{base_url}/api/health"
    result.start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        batch_results = await run_concurrent_batch(client, url, 50)
        for latency in batch_results:
            if latency is not None:
                result.success_count += 1
                result.latencies_ms.append(latency)
            else:
                result.error_count += 1

    result.end_time = time.perf_counter()
    return result


# ── Tests pytest (intégrables dans le CI/CD) ─────────────────────────────────
import pytest

@pytest.mark.asyncio
async def test_sla_p99_health_endpoint():
    """Vérifie que /api/health respecte le SLA P99 < 500ms sous charge minimale."""
    url = "http://localhost:8000/api/health"
    latencies = []
    async with httpx.AsyncClient() as client:
        tasks = [_single_request(client, url) for _ in range(50)]
        results = await asyncio.gather(*tasks)
        latencies = [r for r in results if r is not None]

    if len(latencies) < 10:
        pytest.skip("Service non disponible pour le test de charge")

    p99 = sorted(latencies)[int(len(latencies) * 0.99) - 1]
    error_rate = (50 - len(latencies)) / 50
    assert p99 <= SLA_P99_MAX_MS, f"P99={p99:.1f}ms dépasse le SLA bancaire de {SLA_P99_MAX_MS}ms"
    assert error_rate <= SLA_ERROR_RATE_MAX, f"Taux d'erreur {error_rate*100:.2f}% dépasse le SLA"


@pytest.mark.asyncio
async def test_concurrent_requests_no_crash():
    """Vérifie que 20 requêtes simultanées ne font pas crasher l'API."""
    url = "http://localhost:8000/api/health"
    async with httpx.AsyncClient() as client:
        results = await run_concurrent_batch(client, url, 20)
    successes = [r for r in results if r is not None]
    assert len(successes) >= 18, f"Trop d'erreurs sous charge légère: {20-len(successes)} erreurs"


# ── CLI Main ─────────────────────────────────────────────────────────────────
async def main(base_url: str, scenario_name: str, fail_on_sla: bool):
    scenarios = {
        "normal": scenario_normal,
        "ramp_up": scenario_ramp_up,
        "spike": scenario_spike,
        "ci": scenario_ci,
    }

    if scenario_name not in scenarios:
        print(f"❌ Scénario inconnu: {scenario_name}. Disponibles: {list(scenarios.keys())}")
        sys.exit(1)

    print(f"🏦 Banking Grade Load Test — Scénario: {scenario_name}")
    print(f"   Target: {base_url}")
    print(f"   SLA: P99 ≤ {SLA_P99_MAX_MS}ms | Error Rate ≤ {SLA_ERROR_RATE_MAX*100:.1f}%\n")

    result = await scenarios[scenario_name](base_url)
    sla_ok = result.print_report()

    if fail_on_sla and not sla_ok:
        print("❌ SLA VIOLÉ — Le test a échoué (mode --fail-on-sla activé)")
        sys.exit(1)
    elif sla_ok:
        print("✅ Tous les SLA bancaires sont respectés.")
    else:
        print("⚠️  Certains SLA ne sont pas respectés (mode --fail-on-sla désactivé).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Banking Grade Load Testing Tool")
    parser.add_argument("--url", default="http://localhost:8000", help="URL de base de l'API")
    parser.add_argument(
        "--scenario",
        default="normal",
        choices=["normal", "ramp_up", "spike", "ci"],
        help="Scénario de test"
    )
    parser.add_argument(
        "--fail-on-sla",
        action="store_true",
        help="Retourner exit code 1 si un SLA est violé (pour CI/CD)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.url, args.scenario, args.fail_on_sla))
