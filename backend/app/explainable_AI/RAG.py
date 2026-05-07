# ================================================================
# RAG.py - Version améliorée avec prompt système optimisé et
#           structure de réponse enrichie par anomalie individuelle
# ================================================================

import os
import json
import logging
import re
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── MongoDB ──────────────────────────────────────────────────────
try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

# ── ChromaDB ─────────────────────────────────────────────────────
CHROMA_AVAILABLE = False
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    pass

# ── FAISS ────────────────────────────────────────────────────────
FAISS_AVAILABLE = False
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    pass

# ── sentence-transformers ─────────────────────────────────────────
ST_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    pass

# ── PyTorch ──────────────────────────────────────────────────────
TORCH_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    pass

# ================================================================
# CONFIGURATION
# ================================================================
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
CHROMA_PATH = BASE_DIR / "chroma_db"
FAISS_PATH = BASE_DIR / "faiss_index"
RESULTS_DIR.mkdir(exist_ok=True)
CHROMA_PATH.mkdir(exist_ok=True)
FAISS_PATH.mkdir(exist_ok=True)

MONGO_URI     = os.environ.get("MONGO_URI",     "mongodb://localhost:27017")
OLLAMA_URL    = os.environ.get("OLLAMA_URL",    "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL",  "phi3:mini")
EMBED_MODEL   = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "security_knowledge"
TOP_K_DOCS     = 4
MAX_TOKENS     = 900
OLLAMA_TIMEOUT = 120

# Taille des batches MongoDB pour ne pas tout charger en RAM d'un coup
MONGO_BATCH_SIZE = 2000
# 0 = pas de limite (toutes les anomalies)
NO_LIMIT = 0

# ================================================================
# PROMPT SYSTÈME — Expert SOC avec format strict
# ================================================================
SYSTEM_PROMPT = """Tu es un expert en cybersécurité SOC (Security Operations Center). \
Ton rôle est d'analyser des groupes d'anomalies réseau corrélées par type et de produire \
des rapports d'investigation personnalisés.

Instructions strictes :
1. Ne fais AUCUNE introduction, ni conclusion, ni phrase de politesse.
2. Utilise UNIQUEMENT les données fournies (IPs, règles, métriques, protocoles).
3. Respecte SCRUPULEUSEMENT le format de réponse ci-dessous, sans le modifier.
4. Sois précis, technique, concis. Chaque champ doit être rempli.
5. Pour les recommandations, sois actionnable (commandes, configs, délais chiffrés).

FORMAT DE RÉPONSE EXACT (ne pas modifier les libellés) :

la Cause :
[Analyse précise : IP source, type d'attaque, cibles, protocole, règle firewall impactée]

Explication :
[Analyse technique : nombre d'événements, criticité du risque, latence, CPU, packet loss, comportement observé]

Recommandations :

* Immédiat : [Action urgente à exécuter dans les 5 minutes]

* Court terme : [Action de remédiation dans les 24h]

* Prévention : [Configuration ou mesure long terme]

Temps estimé de résolution :
* [Action 1] : ~[X] minutes
* [Action 2] : ~[X] minutes
Temps total estimé : ~[Somme] minutes"""

# ================================================================
# MAPPINGS PIPELINE
# ================================================================
PIPELINE_MONGO_MAP = {
    "firewall": {"db": "firewall_db",     "collection": "detected_anomalies"},
    "os":       {"db": "OS_db",           "collection": "detected_os_anomalies"},
    "app":      {"db": "APP_db",          "collection": "detected_app_anomalies"},
    "apilogs":  {"db": "API_db",          "collection": "detected_api_anomalies"},
    "database": {"db": "basededonne_db",  "collection": "detected_db_anomalies"},
}

PIPELINE_LABELS = {
    "firewall": "Firewall / Réseau",
    "os":       "OS & Infrastructure",
    "app":      "Logs Applicatifs",
    "apilogs":  "API Logs",
    "database": "Base de Données",
}

PIPELINE_DOMAIN_MAP = {
    "firewall": "firewall",
    "os":       "os",
    "app":      "app",
    "apilogs":  "api",
    "database": "db",
}


# ================================================================
# FAISS STORE
# ================================================================
class FaissStore:
    def __init__(self, dim: int = 384):
        self.dim = dim
        self.index = None
        self.documents = []
        self.metadatas = []
        self.ids = []
        self._loaded = False

    def load_or_create(self):
        if not FAISS_AVAILABLE:
            return
        idx_path = FAISS_PATH / "index.faiss"
        meta_path = FAISS_PATH / "meta.json"
        if idx_path.exists() and meta_path.exists():
            try:
                self.index = faiss.read_index(str(idx_path))
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                self.documents = meta["documents"]
                self.metadatas = meta["metadatas"]
                self.ids = meta["ids"]
                self._loaded = True
                return
            except Exception:
                pass
        self.index = faiss.IndexFlatIP(self.dim)

    def upsert(self, ids, documents, embeddings, metadatas):
        if not FAISS_AVAILABLE or self.index is None:
            return False
        try:
            self.index = faiss.IndexFlatIP(self.dim)
            self.documents = documents
            self.metadatas = metadatas
            self.ids = ids
            emb = embeddings.astype(np.float32)
            faiss.normalize_L2(emb)
            self.index.add(emb)
            faiss.write_index(self.index, str(FAISS_PATH / "index.faiss"))
            with open(FAISS_PATH / "meta.json", "w") as f:
                json.dump({"documents": documents, "metadatas": metadatas, "ids": ids}, f)
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"FAISS upsert error: {e}")
            return False

    def query(self, query_embedding, domain, top_k=TOP_K_DOCS):
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return ""
        try:
            q = query_embedding.astype(np.float32).reshape(1, -1)
            faiss.normalize_L2(q)
            distances, indices = self.index.search(q, min(top_k * 2, self.index.ntotal))
            parts = []
            seen = 0
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or seen >= top_k:
                    continue
                meta = self.metadatas[idx]
                if meta.get("domain") not in (domain, "general"):
                    continue
                if dist > 0.25:
                    parts.append(
                        f"[{meta.get('anomaly_type', '?')}]\n{self.documents[idx].strip()[:600]}"
                    )
                    seen += 1
            return "\n\n---\n\n".join(parts)
        except Exception:
            return ""

    @property
    def count(self):
        return self.index.ntotal if (FAISS_AVAILABLE and self.index) else 0


# ================================================================
# RAG ENGINE
# ================================================================
class RAGEngine:
    def __init__(self):
        self._embedder = None
        self._chroma = None
        self._collection = None
        self._faiss = FaissStore()
        self._kb_loaded = False
        self._mongo_client = None
        self._gpu_available = False
        self._progress_callback: Optional[Callable] = None
        self._detect_gpu()

    def _detect_gpu(self):
        if TORCH_AVAILABLE and torch.cuda.is_available():
            self._gpu_available = True
            logger.info(f"✅ GPU: {torch.cuda.get_device_name(0)}")

    # ── MongoDB ──────────────────────────────────────────────────
    def _get_mongo_client(self):
        if self._mongo_client:
            try:
                self._mongo_client.admin.command("ping")
                return self._mongo_client
            except Exception:
                self._mongo_client = None
        if not MONGO_AVAILABLE:
            return None
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            self._mongo_client = client
            return client
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            return None

    # ================================================================
    # RÉCUPÉRATION ET GROUPEMENT PAR TYPE
    # ================================================================
    def fetch_anomalies_grouped_by_type(self, pipeline: str) -> Dict[str, Dict]:
        """
        Récupère TOUTES les anomalies (sans limite) et les groupe par type.
        Utilise un cursor avec batch_size pour éviter de tout charger en RAM.
        """
        config = PIPELINE_MONGO_MAP.get(pipeline)
        if not config:
            return {}

        client = self._get_mongo_client()
        if not client:
            return {}

        try:
            coll = client[config["db"]][config["collection"]]

            # Compter d'abord pour le logging
            total_docs = coll.count_documents({"is_anomaly": 1})
            logger.info(f"[{pipeline}] 📊 {total_docs} anomalies totales à traiter")

            if total_docs == 0:
                return {}

            # Cursor sans limite, lecture par batch
            cursor = coll.find({"is_anomaly": 1}).batch_size(MONGO_BATCH_SIZE)

            groups: Dict[str, Any] = defaultdict(lambda: {
                "count": 0,
                "risks": [],
                "events": [],
                "src_ips": defaultdict(int),
                "dst_ips": defaultdict(int),
                "rules": defaultdict(int),
                "protocols": defaultdict(int),
                "metrics": defaultdict(list),
            })

            processed = 0
            for doc in cursor:
                processed += 1
                if processed % 5000 == 0:
                    logger.info(f"[{pipeline}] ⏳ Groupement : {processed}/{total_docs} docs traités...")

                atype = doc.get("Anomaly_type") or doc.get("anomaly_type") or "Inconnu"
                if not atype or atype in ("Normal", "normal"):
                    continue

                g = groups[atype]
                g["count"] += 1

                risk = doc.get("Risk") or doc.get("risk") or 0
                if isinstance(risk, (int, float)):
                    g["risks"].append(float(risk))

                # Garder jusqu'à 5 exemples représentatifs
                if len(g["events"]) < 5:
                    doc_copy = {k: v for k, v in doc.items() if k != "_id"}
                    doc_copy["_id"] = str(doc["_id"])
                    g["events"].append(doc_copy)

                # IPs
                for field, dest in [
                    ("Src_ip", "src_ips"), ("src_ip", "src_ips"),
                    ("Dst_ip", "dst_ips"), ("dst_ip", "dst_ips"),
                ]:
                    val = doc.get(field)
                    if val:
                        g[dest][val] += 1

                # Règles firewall
                for field in ("Firewall_rule_id", "rule_id", "firewall_rule"):
                    val = doc.get(field)
                    if val:
                        g["rules"][str(val)] += 1
                        break

                # Protocole
                proto = doc.get("Protocol") or doc.get("protocol")
                if proto:
                    g["protocols"][proto] += 1

                # Métriques numériques
                for metric in (
                    "Latency_ms", "latency_ms",
                    "Packet_loss_pct", "packet_loss_pct",
                    "cpu_usage_percent", "memory_usage_percent",
                    "response_time_ms", "bytes_sent", "packet_count",
                ):
                    val = doc.get(metric)
                    if isinstance(val, (int, float)):
                        g["metrics"][metric].append(float(val))

            logger.info(f"[{pipeline}] ✅ Groupement terminé : {processed} docs → {len(groups)} types")

            # Consolider
            result = {}
            for atype, data in groups.items():
                risks = data["risks"]
                result[atype] = {
                    "anomaly_type": atype,
                    "count": data["count"],
                    "risk_avg":  round(sum(risks) / len(risks), 2) if risks else 0,
                    "risk_max":  max(risks) if risks else 0,
                    "risk_min":  min(risks) if risks else 0,
                    "critical_count": len([r for r in risks if r >= 8]),
                    "top_src_ips": dict(
                        sorted(data["src_ips"].items(), key=lambda x: x[1], reverse=True)[:5]
                    ),
                    "top_dst_ips": dict(
                        sorted(data["dst_ips"].items(), key=lambda x: x[1], reverse=True)[:5]
                    ),
                    "top_rules": dict(
                        sorted(data["rules"].items(), key=lambda x: x[1], reverse=True)[:3]
                    ),
                    "top_protocols": dict(
                        sorted(data["protocols"].items(), key=lambda x: x[1], reverse=True)[:3]
                    ),
                    "sample_events": data["events"],
                    "metrics": {
                        metric: {
                            "avg": round(sum(vals) / len(vals), 2),
                            "max": max(vals),
                            "min": min(vals),
                        }
                        for metric, vals in data["metrics"].items() if vals
                    },
                }

            logger.info(f"[{pipeline}] {sum(v['count'] for v in result.values())} anomalies "
                        f"→ {len(result)} types")
            return result

        except Exception as e:
            logger.error(f"fetch_anomalies_grouped_by_type error: {e}")
            import traceback; traceback.print_exc()
            return {}

    # ================================================================
    # EMBEDDER & VECTOR STORES
    # ================================================================
    def _init_embedder(self):
        if self._embedder or not ST_AVAILABLE:
            return
        try:
            device = "cuda" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
            self._embedder = SentenceTransformer(EMBED_MODEL, device=device)
            logger.info(f"Embedder loaded on {device}")
        except Exception as e:
            logger.error(f"Embedder init error: {e}")

    def _init_chroma(self) -> bool:
        if self._chroma or not CHROMA_AVAILABLE:
            return False
        try:
            self._chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
            self._collection = self._chroma.get_or_create_collection(name=COLLECTION_NAME)
            logger.info("ChromaDB initialized")
            return True
        except Exception as e:
            logger.error(f"ChromaDB init error: {e}")
            return False

    def load_knowledge_base(self, force_reload: bool = False) -> bool:
        if self._kb_loaded and not force_reload:
            return True
        self._init_embedder()
        if not self._embedder:
            return False
        try:
            from knowledge_base import get_all_documents
        except ImportError:
            try:
                from explainable_AI.knowledge_base import get_all_documents
            except ImportError:
                logger.error("knowledge_base.py not found")
                return False

        docs = get_all_documents()
        texts = [d["content"] for d in docs]
        ids = [d["id"] for d in docs]
        metas = [{"domain": d["domain"], "anomaly_type": d["anomaly_type"]} for d in docs]

        embeddings = self._embedder.encode(
            texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True
        )

        if CHROMA_AVAILABLE and self._init_chroma():
            try:
                self._collection.upsert(
                    ids=ids, documents=texts,
                    embeddings=embeddings.tolist(), metadatas=metas
                )
                logger.info(f"ChromaDB: {self._collection.count()} docs")
            except Exception as e:
                logger.error(f"ChromaDB upsert error: {e}")

        if FAISS_AVAILABLE:
            try:
                self._faiss.load_or_create()
                self._faiss.upsert(ids, texts, embeddings, metas)
            except Exception as e:
                logger.error(f"FAISS upsert error: {e}")

        self._kb_loaded = True
        return True

    def retrieve_context(self, anomaly_type: str, pipeline: str) -> str:
        if not self._embedder or not self._kb_loaded:
            return ""
        try:
            query = f"{anomaly_type} {pipeline} sécurité réseau investigation remédiation"
            q_emb = self._embedder.encode([query], normalize_embeddings=True)
            domain = PIPELINE_DOMAIN_MAP.get(pipeline, "general")

            if CHROMA_AVAILABLE and self._collection and self._collection.count() > 0:
                try:
                    results = self._collection.query(
                        query_embeddings=q_emb.tolist(),
                        n_results=TOP_K_DOCS,
                        where={"domain": {"$in": [domain, "general"]}},
                    )
                    if results["documents"] and results["documents"][0]:
                        return "\n\n".join(results["documents"][0][:2])
                except Exception:
                    pass

            if FAISS_AVAILABLE and self._faiss.count > 0:
                return self._faiss.query(q_emb[0], domain, TOP_K_DOCS)
            return ""
        except Exception:
            return ""

    # ================================================================
    # APPEL OLLAMA
    # ================================================================
    def _call_ollama(self, prompt: str) -> str:
        """Appel LLM avec le system prompt et les données d'analyse."""
        try:
            full_prompt = f"{SYSTEM_PROMPT}\n\nDonnées à analyser :\n{prompt}"
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": MAX_TOKENS,
                    "temperature": 0.25,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                },
            }
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            return f"ERREUR HTTP {resp.status_code}"
        except Exception as e:
            return f"ERREUR: {str(e)}"

    # ================================================================
    # CONSTRUCTION DU PROMPT PAR TYPE
    # ================================================================
    def _build_type_prompt(
        self, type_data: Dict, pipeline: str, rag_context: str
    ) -> str:
        atype      = type_data["anomaly_type"]
        count      = type_data["count"]
        risk_avg   = type_data["risk_avg"]
        risk_max   = type_data["risk_max"]
        critical   = type_data["critical_count"]

        lines = [
            f"Type d'anomalie : {atype}",
            f"Pipeline        : {PIPELINE_LABELS.get(pipeline, pipeline)}",
            f"Nombre total    : {count} événements",
            f"Score de risque : {risk_avg}/10 (moyenne) | {risk_max}/10 (maximum) | {critical} critiques",
        ]

        # IPs sources
        if type_data.get("top_src_ips"):
            ips = list(type_data["top_src_ips"].items())[:3]
            lines.append("IP Sources principales : " + ", ".join(f"{ip} ({n}x)" for ip, n in ips))

        # IPs destinations
        if type_data.get("top_dst_ips"):
            ips = list(type_data["top_dst_ips"].items())[:3]
            lines.append("IP Destinations principales : " + ", ".join(f"{ip} ({n}x)" for ip, n in ips))

        # Règles firewall
        if type_data.get("top_rules"):
            rules = list(type_data["top_rules"].keys())[:2]
            lines.append(f"Règles firewall impactées : {', '.join(rules)}")

        # Protocoles
        if type_data.get("top_protocols"):
            protos = list(type_data["top_protocols"].keys())[:3]
            lines.append(f"Protocoles : {', '.join(protos)}")

        # Métriques
        metrics = type_data.get("metrics", {})
        metric_labels = {
            "Latency_ms": "Latence", "latency_ms": "Latence",
            "Packet_loss_pct": "Perte paquets", "packet_loss_pct": "Perte paquets",
            "cpu_usage_percent": "CPU", "memory_usage_percent": "Mémoire",
            "response_time_ms": "Temps réponse", "bytes_sent": "Bytes envoyés",
            "packet_count": "Nb paquets",
        }
        seen_labels = set()
        for key, label in metric_labels.items():
            if key in metrics and label not in seen_labels:
                m = metrics[key]
                unit = "%" if "pct" in key or "percent" in key else ("ms" if "ms" in key else "")
                lines.append(f"{label} : moy={m['avg']}{unit}, max={m['max']}{unit}")
                seen_labels.add(label)

        # Exemple concret
        sample = (type_data.get("sample_events") or [{}])[0]
        if sample:
            ex_parts = []
            for field, label in [
                ("Src_ip", "IP Source"), ("src_ip", "IP Source"),
                ("Dst_ip", "IP Destination"), ("dst_ip", "IP Destination"),
                ("Protocol", "Protocole"), ("protocol", "Protocole"),
                ("Firewall_rule_id", "Règle"), ("rule_id", "Règle"),
                ("Risk", "Risque"), ("risk", "Risque"),
            ]:
                val = sample.get(field)
                if val is not None and label not in [p.split(":")[0] for p in ex_parts]:
                    ex_parts.append(f"{label}: {val}")
            if ex_parts:
                lines.append("\nExemple d'événement concret :")
                lines.extend(f"  {p}" for p in ex_parts[:6])

        # Contexte RAG
        if rag_context:
            lines.append(f"\nBase de connaissances SOC :\n{rag_context[:600]}")

        return "\n".join(lines)

    # ================================================================
    # PARSER LA RÉPONSE IA → STRUCTURE
    # ================================================================
    @staticmethod
    def _parse_analysis(text: str) -> Dict[str, Optional[str]]:
        """Extrait les sections du rapport IA structuré."""
        result = {
            "cause": None,
            "explication": None,
            "recommandations": None,
            "temps_total": None,
            "full_analysis": text,
        }

        # Cause
        m = re.search(
            r"la\s+Cause\s*:?\s*([\s\S]*?)(?=\nExplication\s*:|$)",
            text, re.IGNORECASE
        )
        if m:
            result["cause"] = m.group(1).strip()

        # Explication
        m = re.search(
            r"Explication\s*:?\s*([\s\S]*?)(?=\nRecommandations?\s*:|$)",
            text, re.IGNORECASE
        )
        if m:
            result["explication"] = m.group(1).strip()

        # Recommandations
        m = re.search(
            r"Recommandations?\s*:?\s*([\s\S]*?)(?=\nTemps estimé|$)",
            text, re.IGNORECASE
        )
        if m:
            result["recommandations"] = m.group(1).strip()

        # Temps estimé
        m = re.search(
            r"Temps estimé[^:]*:\s*([\s\S]*?)$",
            text, re.IGNORECASE
        )
        if m:
            result["temps_total"] = m.group(1).strip()

        return result

    # ================================================================
    # ANALYSE PRINCIPALE DU PIPELINE
    # ================================================================
    def analyze_pipeline(self, pipeline: str) -> Dict[str, Any]:
        t_start = datetime.now()

        result: Dict[str, Any] = {
            "pipeline":      pipeline,
            "label":         PIPELINE_LABELS.get(pipeline, pipeline),
            "analyzed_at":   t_start.isoformat(),
            "model":         OLLAMA_MODEL,
            "status":        "running",
            "global_stats":  {},
            "type_analyses": {},
            "all_anomalies": [],
            "errors":        [],
            "performance":   {},
        }

        logger.info("=" * 60)
        logger.info(f"[{pipeline}] 🚀 Analyse par type — début")
        logger.info("=" * 60)

        # 1. Charger la knowledge base
        logger.info(f"[{pipeline}] 📚 Chargement KB...")
        self.load_knowledge_base()

        # 2. Récupérer et grouper les anomalies
        logger.info(f"[{pipeline}] 📡 Récupération MongoDB...")
        grouped = self.fetch_anomalies_grouped_by_type(pipeline)

        if not grouped:
            result["status"] = "done"
            result["message"] = "Aucune anomalie trouvée"
            return result

        # 3. Stats globales
        total_anomalies = sum(t["count"] for t in grouped.values())
        all_risks = [t["risk_avg"] for t in grouped.values() if t.get("risk_avg")]
        critical_total = sum(t["critical_count"] for t in grouped.values())

        result["global_stats"] = {
            "total_anomalies": total_anomalies,
            "types_count":     len(grouped),
            "avg_risk":        round(sum(all_risks) / len(all_risks), 2) if all_risks else 0,
            "risk_avg":        round(sum(all_risks) / len(all_risks), 2) if all_risks else 0,
            "critical_count":  critical_total,
        }

        logger.info(f"[{pipeline}] {total_anomalies} anomalies, {len(grouped)} types, "
                    f"{critical_total} critiques")

        # 4. Analyser chaque type avec Ollama
        logger.info(f"[{pipeline}] 🤖 Génération des rapports IA...")
        type_items = list(grouped.items())
        total_types = len(type_items)

        for i, (atype, type_data) in enumerate(type_items, 1):
            if self._progress_callback:
                try:
                    self._progress_callback(atype, i, total_types)
                except Exception:
                    pass

            logger.info(
                f"[{pipeline}] 🔍 [{i}/{total_types}] {atype} "
                f"({type_data['count']} anomalies, risk_avg={type_data['risk_avg']})"
            )

            try:
                rag_context  = self.retrieve_context(atype, pipeline)
                prompt_data  = self._build_type_prompt(type_data, pipeline, rag_context)
                raw_response = self._call_ollama(prompt_data)
                parsed       = self._parse_analysis(raw_response)

                result["type_analyses"][atype] = {
                    "anomaly_type":    atype,
                    "count":           type_data["count"],
                    "risk_avg":        type_data["risk_avg"],
                    "risk_max":        type_data["risk_max"],
                    "risk_min":        type_data["risk_min"],
                    "critical_count":  type_data["critical_count"],
                    "top_src_ips":     type_data.get("top_src_ips", {}),
                    "top_dst_ips":     type_data.get("top_dst_ips", {}),
                    "top_rules":       type_data.get("top_rules", {}),
                    "top_protocols":   type_data.get("top_protocols", {}),
                    "metrics":         type_data.get("metrics", {}),
                    # Champs parsés
                    "cause":           parsed["cause"],
                    "explication":     parsed["explication"],
                    "recommandations": parsed["recommandations"],
                    "temps_total":     parsed["temps_total"],
                    "full_analysis":   parsed["full_analysis"],
                    "rag_used":        bool(rag_context),
                }

                logger.info(f"[{pipeline}] ✅ [{i}/{total_types}] Terminé")

            except Exception as e:
                logger.error(f"[{pipeline}] ❌ Erreur {atype}: {e}")
                result["errors"].append({"type": atype, "error": str(e)})
                result["type_analyses"][atype] = {
                    "anomaly_type":  atype,
                    "count":         type_data["count"],
                    "full_analysis": f"Erreur: {str(e)}",
                    "cause": None, "explication": None,
                    "recommandations": None, "temps_total": None,
                }

        # 5. Récupérer TOUTES les anomalies individuelles et enrichir avec le rapport de leur type
        logger.info(f"[{pipeline}] 📋 Enrichissement de toutes les anomalies individuelles...")
        try:
            client = self._get_mongo_client()
            if client:
                config = PIPELINE_MONGO_MAP.get(pipeline)
                if config:
                    coll = client[config["db"]][config["collection"]]
                    # Cursor sans limite, batch pour la RAM
                    all_cursor = coll.find({"is_anomaly": 1}).batch_size(MONGO_BATCH_SIZE)
                    all_docs = []
                    enriched = 0
                    for doc in all_cursor:
                        doc["_id"] = str(doc["_id"])
                        atype = doc.get("Anomaly_type") or doc.get("anomaly_type") or "Inconnu"
                        type_analysis = result["type_analyses"].get(atype)
                        if type_analysis:
                            doc["_type_analysis_ref"] = atype
                            doc["cause"]           = type_analysis.get("cause")
                            doc["explication"]     = type_analysis.get("explication")
                            doc["recommandations"] = type_analysis.get("recommandations")
                            doc["temps_total"]     = type_analysis.get("temps_total")
                            doc["full_analysis"]   = type_analysis.get("full_analysis")
                            enriched += 1
                        all_docs.append(doc)
                    result["all_anomalies"] = all_docs
                    logger.info(f"[{pipeline}] {len(all_docs)} anomalies récupérées, {enriched} enrichies avec rapport IA")
        except Exception as e:
            logger.error(f"Erreur enrichissement anomalies: {e}")

        # 6. Finaliser
        total_elapsed = (datetime.now() - t_start).total_seconds()
        result["performance"] = {
            "total_duration_s":  round(total_elapsed, 1),
            "types_analyzed":    len(result["type_analyses"]),
            "errors_count":      len(result["errors"]),
        }
        result["status"] = "done"

        # Sauvegarder
        out_path = RESULTS_DIR / f"{pipeline}_analysis.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        logger.info("=" * 60)
        logger.info(
            f"[{pipeline}] 🎉 Analyse terminée en {total_elapsed:.1f}s "
            f"— {len(result['type_analyses'])} types analysés"
        )
        logger.info("=" * 60)

        return result

    # ================================================================
    # UTILITAIRES
    # ================================================================
    def get_cached_result(self, pipeline: str) -> Optional[Dict]:
        out_path = RESULTS_DIR / f"{pipeline}_analysis.json"
        if out_path.exists():
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def check_mongodb(self) -> Dict:
        client = self._get_mongo_client()
        if not client:
            return {"mongodb_running": False}
        try:
            stats = {}
            for pipeline, config in PIPELINE_MONGO_MAP.items():
                try:
                    count = client[config["db"]][config["collection"]].count_documents(
                        {"is_anomaly": 1}
                    )
                    stats[pipeline] = {"anomalies": count}
                except Exception:
                    stats[pipeline] = {"error": "Accès impossible"}
            return {"mongodb_running": True, "pipelines": stats}
        except Exception:
            return {"mongodb_running": False}

    def check_ollama(self) -> Dict:
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {
                    "ollama_running":  True,
                    "model_available": OLLAMA_MODEL in models,
                    "available_models": models,
                }
            return {"ollama_running": False}
        except Exception:
            return {"ollama_running": False}

    def reload_knowledge_base(self) -> bool:
        self._kb_loaded = False
        self._faiss = FaissStore()
        return self.load_knowledge_base(force_reload=True)


# ── Singleton ────────────────────────────────────────────────────
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine