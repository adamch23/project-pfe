# ================================================================
# RAG_debug.py - Diagnostic avancé avec timeouts et logs détaillés
# ================================================================

import os
import sys
import time
import threading
import traceback
from pathlib import Path

# Ajouter le chemin parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=" * 70)
print("DIAGNOSTIC RAG AVANCÉ - Recherche du problème exact")
print("=" * 70)

# 1. Vérification environnement
print("\n[1] Vérification environnement...")
print(f"Python: {sys.version}")
print(f"Chemin: {os.getcwd()}")

# 2. Test des imports
print("\n[2] Test des imports...")
imports_status = {}

for module in ["pandas", "numpy", "requests", "pymongo", "torch", "sentence_transformers", "chromadb", "faiss"]:
    try:
        if module == "torch":
            exec(f"import {module}")
            print(f"✅ {module} OK - CUDA: {torch.cuda.is_available()}")
        elif module == "sentence_transformers":
            exec(f"from {module} import SentenceTransformer")
            print(f"✅ {module} OK")
        else:
            exec(f"import {module}")
            print(f"✅ {module} OK")
        imports_status[module] = True
    except Exception as e:
        print(f"❌ {module}: {e}")
        imports_status[module] = False

# 3. Test knowledge_base
print("\n[3] Test chargement knowledge_base...")
try:
    from knowledge_base import get_all_documents
    docs = get_all_documents()
    print(f"✅ knowledge_base OK - {len(docs)} documents")
except ImportError:
    try:
        from explainable_AI.knowledge_base import get_all_documents
        docs = get_all_documents()
        print(f"✅ explainable_AI.knowledge_base OK - {len(docs)} documents")
    except ImportError as e:
        print(f"❌ knowledge_base: {e}")
        docs = []
except Exception as e:
    print(f"❌ knowledge_base: {e}")
    docs = []

# 4. Test embedder avec timing
print("\n[4] Test embedder...")
embedder = None
if imports_status.get("sentence_transformers", False):
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"   Device: {device}")
        
        t0 = time.time()
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)
        t1 = time.time()
        print(f"✅ Embedder chargé en {t1-t0:.1f}s sur {device}")
        
        t0 = time.time()
        test_embed = embedder.encode(["test"], normalize_embeddings=True)
        t1 = time.time()
        print(f"✅ Test encodage OK en {t1-t0:.3f}s - dimension: {test_embed.shape}")
    except Exception as e:
        print(f"❌ Erreur embedder: {e}")
        traceback.print_exc()
else:
    print("   Skip - sentence_transformers non disponible")

# 5. Test ChromaDB avec timeout explicite
print("\n[5] Test ChromaDB avec timeout...")
chroma_ok = False
if embedder is not None and docs and imports_status.get("chromadb", False):
    try:
        import chromadb
        from chromadb.config import Settings
        
        chroma_path = Path("chroma_db_test")
        chroma_path.mkdir(exist_ok=True)
        
        print("   Création client ChromaDB...")
        t0 = time.time()
        chroma_client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        t1 = time.time()
        print(f"✅ Client ChromaDB créé en {t1-t0:.2f}s")
        
        collection_name = "test_security_knowledge"
        try:
            chroma_client.delete_collection(collection_name)
            print("   Ancienne collection supprimée")
        except:
            pass
        
        print("   Création collection...")
        t0 = time.time()
        collection = chroma_client.create_collection(name=collection_name)
        t1 = time.time()
        print(f"✅ Collection créée en {t1-t0:.2f}s")
        
        texts = [d["content"] for d in docs]
        ids = [d["id"] for d in docs]
        metas = [{"domain": d["domain"], "anomaly_type": d["anomaly_type"]} for d in docs]
        
        print(f"   Génération embeddings pour {len(texts)} documents...")
        t0 = time.time()
        embeddings = embedder.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
        t1 = time.time()
        print(f"✅ Embeddings générés en {t1-t0:.1f}s - shape: {embeddings.shape}")
        
        # Test upsert avec timeout
        print("   Upsert dans ChromaDB (timeout 30s)...")
        
        upsert_completed = [False]
        upsert_error = [None]
        
        def do_upsert():
            try:
                collection.upsert(
                    ids=ids, 
                    documents=texts, 
                    embeddings=embeddings.tolist(), 
                    metadatas=metas
                )
                upsert_completed[0] = True
            except Exception as e:
                upsert_error[0] = e
        
        upsert_thread = threading.Thread(target=do_upsert)
        upsert_thread.daemon = True
        upsert_thread.start()
        upsert_thread.join(timeout=30)
        
        if upsert_thread.is_alive():
            print("❌ ChromaDB upsert TIMEOUT après 30s - Le processus bloque!")
            print("   C'est le problème principal !")
        elif upsert_error[0]:
            print(f"❌ ChromaDB upsert ERREUR: {upsert_error[0]}")
        else:
            print(f"✅ ChromaDB upsert OK - {collection.count()} documents")
            chroma_ok = True
            
    except Exception as e:
        print(f"❌ Erreur ChromaDB: {e}")
        traceback.print_exc()
else:
    print("   Skip - conditions non remplies pour ChromaDB")

# 6. Test FAISS
print("\n[6] Test FAISS...")
faiss_ok = False
if embedder is not None and docs and imports_status.get("faiss", False):
    try:
        import faiss
        import numpy as np
        
        texts = [d["content"] for d in docs]
        
        print(f"   Génération embeddings...")
        t0 = time.time()
        embeddings = embedder.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
        t1 = time.time()
        print(f"   Embeddings shape: {embeddings.shape} - temps: {t1-t0:.1f}s")
        
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        print(f"✅ Index FAISS créé (dim={dim})")
        
        emb_array = embeddings.astype(np.float32)
        faiss.normalize_L2(emb_array)
        
        print("   Ajout à FAISS...")
        t0 = time.time()
        index.add(emb_array)
        t1 = time.time()
        print(f"✅ FAISS add OK en {t1-t0:.3f}s - {index.ntotal} vecteurs")
        
        # Test recherche
        query_embed = embedder.encode(["test query"], normalize_embeddings=True)
        q = query_embed.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(q)
        t0 = time.time()
        distances, indices = index.search(q, 5)
        t1 = time.time()
        print(f"✅ FAISS search OK en {t1-t0:.3f}s - distances: {distances[0][:2]}")
        faiss_ok = True
        
    except Exception as e:
        print(f"❌ Erreur FAISS: {e}")
        traceback.print_exc()
else:
    print("   Skip - conditions non remplies pour FAISS")

# 7. Test Ollama
print("\n[7] Test Ollama...")
ollama_ok = False
try:
    import requests
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    print(f"   URL: {ollama_url}")
    
    t0 = time.time()
    resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
    t1 = time.time()
    print(f"✅ Ollama accessible en {t1-t0:.2f}s - status: {resp.status_code}")
    
    models = resp.json().get("models", [])
    model_names = [m["name"] for m in models]
    print(f"   Modèles: {model_names}")
    
    # Test generation avec timeout
    test_payload = {
        "model": "phi3:mini",
        "prompt": "Réponds par OK",
        "stream": False,
        "options": {"num_predict": 10}
    }
    print("   Test génération (timeout 30s)...")
    t0 = time.time()
    resp2 = requests.post(f"{ollama_url}/api/generate", json=test_payload, timeout=30)
    t1 = time.time()
    if resp2.status_code == 200:
        print(f"✅ Génération OK en {t1-t0:.2f}s - réponse: {resp2.json().get('response', '')[:50]}")
        ollama_ok = True
    else:
        print(f"❌ Génération erreur: {resp2.status_code}")
    
except Exception as e:
    print(f"❌ Erreur Ollama: {e}")

# 8. Test du vrai RAGEngine
print("\n[8] Test du vrai RAGEngine (votre fichier)...")
try:
    # Nettoyer les caches Python
    if 'explainable_AI.RAG' in sys.modules:
        del sys.modules['explainable_AI.RAG']
    if 'RAG' in sys.modules:
        del sys.modules['RAG']
    
    from explainable_AI.RAG import get_rag_engine
    print("✅ Import RAGEngine OK")
    
    engine = get_rag_engine()
    print("✅ RAGEngine instancié")
    
    # Test KB loading avec monitoring
    print("\n   Test load_knowledge_base (avec monitoring)...")
    
    loading_completed = [False]
    loading_error = [None]
    last_log = [time.time()]
    
    def monitor():
        while not loading_completed[0] and loading_error[0] is None:
            elapsed = time.time() - last_log[0]
            if elapsed > 10:
                print(f"   ⏳ Chargement KB toujours en cours... ({int(elapsed)}s)")
                last_log[0] = time.time()
            time.sleep(2)
    
    def do_load():
        try:
            result = engine.load_knowledge_base()
            loading_completed[0] = result
        except Exception as e:
            loading_error[0] = e
    
    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    t0 = time.time()
    load_thread = threading.Thread(target=do_load)
    load_thread.daemon = True
    load_thread.start()
    load_thread.join(timeout=60)
    
    if load_thread.is_alive():
        print(f"❌ load_knowledge_base TIMEOUT après 60s - Bloqué!")
        print("   Le problème est dans load_knowledge_base()")
    elif loading_error[0]:
        print(f"❌ load_knowledge_base ERREUR: {loading_error[0]}")
        traceback.print_exception(type(loading_error[0]), loading_error[0], loading_error[0].__traceback__)
    else:
        t1 = time.time()
        print(f"✅ load_knowledge_base terminé en {t1-t0:.1f}s - résultat: {loading_completed[0]}")
    
    # Test MongoDB
    print("\n   Test check_mongodb...")
    t0 = time.time()
    mongo_result = engine.check_mongodb()
    t1 = time.time()
    print(f"✅ MongoDB check en {t1-t0:.2f}s - running: {mongo_result.get('mongodb_running', False)}")
    
    # Test Ollama
    print("   Test check_ollama...")
    t0 = time.time()
    ollama_result = engine.check_ollama()
    t1 = time.time()
    print(f"✅ Ollama check en {t1-t0:.2f}s - running: {ollama_result.get('ollama_running', False)}")
    
except Exception as e:
    print(f"❌ Erreur RAGEngine: {e}")
    traceback.print_exc()

# 9. Conclusion
print("\n" + "=" * 70)
print("RÉSUMÉ DU DIAGNOSTIC")
print("=" * 70)

print(f"""
┌─────────────────────────────────────────────────────────────────┐
│                      ÉTAT DES COMPOSANTS                         │
├─────────────────────────────────────────────────────────────────┤
│  ChromaDB disponible: {imports_status.get('chromadb', False)}                                         │
│  ChromaDB upsert OK:   {chroma_ok}                                         │
│  FAISS disponible:     {imports_status.get('faiss', False)}                                         │
│  FAISS OK:             {faiss_ok}                                         │
│  Ollama OK:            {ollama_ok}                                         │
│  MongoDB OK:           {mongo_result.get('mongodb_running', False) if 'mongo_result' in dir() else False}                                         │
└─────────────────────────────────────────────────────────────────┘
""")

if not chroma_ok:
    print("\n⚠️ PROBLÈME IDENTIFIÉ: ChromaDB upsert bloque ou timeout!")
    print("   Solution: Désactiver ChromaDB en modifiant CHROMA_AVAILABLE = False dans RAG.py")
    print("   ou utiliser un thread avec timeout pour l'upsert.")

print("\n" + "=" * 70)
print("DIAGNOSTIC TERMINÉ")
print("=" * 70)