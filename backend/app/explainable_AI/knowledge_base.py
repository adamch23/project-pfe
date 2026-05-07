# ================================================================
# knowledge_base.py - Base de connaissances sécurité
# Fichier : backend/app/explainable_AI/knowledge_base.py
# ================================================================

SECURITY_KNOWLEDGE = [
    # ========== FIREWALL ==========
    {
        "id": "fw_ddos_001",
        "domain": "firewall",
        "anomaly_type": "DDoS",
        "content": """
DDoS (Distributed Denial of Service) sur pare-feu.
Indicateurs: packet_count > 5000, concurrent_connections > 5000, bytes_sent > 1M.
Cause: saturation volontaire des ressources réseau par flux massif de paquets.
Actions immédiates: rate-limiting, blocage IP sources, activation mode scrubbing.
Corrélation: saturation CPU sur OS, timeouts DB, erreurs 5xx.
        """
    },
    {
        "id": "fw_scan_001",
        "domain": "firewall",
        "anomaly_type": "Scan reseau",
        "content": """
Scan réseau détecté. Indicateurs: packet_count < 20, multiples connexions vers différents ports.
Cause: reconnaissance réseau automatisée (Nmap, Masscan), peut précéder une intrusion.
Actions: bloquer IP source, activer journalisation, vérifier scan distribué.
Corrélation: si scan suivi de tentatives connexion OS → kill chain active.
        """
    },
    {
        "id": "fw_port_001",
        "domain": "firewall",
        "anomaly_type": "Port inhabituel",
        "content": """
Communication sur port non standard. Cause: malware utilisant ports dynamiques pour C&C, tunnel non autorisé.
Actions: bloquer le port, capturer le trafic, identifier application source sur l'hôte.
Corrélation: vérifier processus actifs sur IP source interne.
        """
    },
    
    # ========== OS ==========
    {
        "id": "os_cpu_001",
        "domain": "os",
        "anomaly_type": "Saturation CPU",
        "content": """
Saturation CPU > 90%. Cause: crypto-miner, processus runaway, force brute.
Actions: identifier processus responsable (top/htop), kill si malveillant.
Corrélation: souvent liée à DDoS firewall ou abus API.
        """
    },
    {
        "id": "os_memory_001",
        "domain": "os",
        "anomaly_type": "Fuite memoire",
        "content": """
Fuite mémoire détectée. Indicateurs: memory_usage > 90% en croissance continue.
Cause: application avec fuite mémoire, sessions non fermées, cache mal géré.
Actions: identifier processus consommateur, redémarrage contrôlé du service.
Prévention: limites mémoire par conteneur, monitoring à 80%.
        """
    },
    {
        "id": "os_login_001",
        "domain": "os",
        "anomaly_type": "Tentatives connexion suspectes",
        "content": """
Tentatives de connexion suspectes >5 échecs. Cause: brute force SSH/RDP.
Actions: bloquer IP source (fail2ban), verrouiller compte ciblé.
Prévention: fail2ban, MFA obligatoire, accès SSH par clé uniquement.
        """
    },
    
    # ========== APP ==========
    {
        "id": "app_5xx_001",
        "domain": "app",
        "anomaly_type": "Erreur serveur (5xx)",
        "content": """
Erreurs serveur 5xx détectées. Cause: exception non gérée, dépendance externe indisponible.
Actions: vérifier logs d'application, rollback si post-déploiement.
Prévention: tests de régression automatisés, circuit breaker.
        """
    },
    {
        "id": "app_ratelimit_001",
        "domain": "app",
        "anomaly_type": "Rate Limit",
        "content": """
Dépassement de rate limit. Indicateurs: status_code=429, requests_per_minute > 400.
Cause: scraping automatisé, abus intentionnel.
Actions: identifier user_id, bloquer si abus avéré.
Prévention: exponential backoff, quotas par profil.
        """
    },
    {
        "id": "app_timeout_001",
        "domain": "app",
        "anomaly_type": "Timeout DB",
        "content": """
Timeout base de données. Cause: requête non optimisée, index manquant, lock contention.
Actions: identifier requête lente, ajouter index manquants.
Prévention: query review, connection pooling, cache Redis.
        """
    },
    
    # ========== API ==========
    {
        "id": "api_abuse_001",
        "domain": "api",
        "anomaly_type": "Abuse API",
        "content": """
Abus d'API détecté. Indicateurs: requests_per_minute_user > 400, status_code=429.
Cause: bot automatisé, scraping massif, L7 DDoS.
Actions: bloquer temporairement user_id, analyser pattern.
Prévention: API gateway avec rate limiting, CAPTCHA, OAuth 2.0.
        """
    },
    {
        "id": "api_timeout_001",
        "domain": "api",
        "anomaly_type": "Timeout",
        "content": """
Timeout API. Cause: requête DB lente, service externe lent, surcharge serveur.
Actions: identifier endpoint, vérifier DB (slow query log).
Prévention: timeout configurés, circuit breaker, mode dégradé.
        """
    },
    {
        "id": "api_traffic_001",
        "domain": "api",
        "anomaly_type": "Explosion trafic",
        "content": """
Explosion soudaine du trafic. Cause: événement viral, bot/crawler massif, DDoS L7.
Actions: activer throttling global, identifier source, scaling horizontal.
        """
    },
    
    # ========== DATABASE ==========
    {
        "id": "db_slow_001",
        "domain": "db",
        "anomaly_type": "Requete lente",
        "content": """
Requête SQL lente >500ms. Cause: absence d'index, statistiques obsolètes.
Actions: EXPLAIN ANALYZE, ajouter index, UPDATE STATISTICS.
Prévention: query review CI/CD, slow query log actif.
        """
    },
    {
        "id": "db_deadlock_001",
        "domain": "db",
        "anomaly_type": "Deadlock",
        "content": """
Deadlock détecté. Cause: ordre d'acquisition des verrous incohérent, transactions longues.
Actions: identifier transactions, retry automatique avec backoff.
Prévention: revoir l'ordre d'accès aux tables, timeout de transaction.
        """
    },
    {
        "id": "db_saturation_001",
        "domain": "db",
        "anomaly_type": "Saturation DB",
        "content": """
Saturation DB - ressources épuisées. Cause: charge excessive, requêtes lentes, vacuum intensif.
Actions: identifier requêtes consommatrices, annuler les non critiques.
Prévention: read replicas, CQRS pattern, monitoring CPU/RAM/IOPS.
        """
    },
    
    # ========== GENERAL ==========
    {
        "id": "gen_killchain_001",
        "domain": "general",
        "anomaly_type": "Kill Chain",
        "content": """
Corrélation multi-pipelines - Kill Chain complète.
Séquences typiques:
- Firewall: Scan réseau → Port inhabituel → DDoS
- OS: Tentatives connexion → Escalade privilèges → Malware
- API: Abuse API → Timeout
- DB: Injection SQL → Comportement anormal
Priorité P1 si ≥3 pipelines affectés simultanément.
        """
    },
    {
        "id": "gen_incident_001",
        "domain": "general",
        "anomaly_type": "Plan reponse",
        "content": """
Plan de réponse aux incidents (PICERL):
1. Préparation: playbooks, contacts d'urgence
2. Identification: classifier sévérité (P1-P4)
3. Confinement: isolation, préservation preuves
4. Éradication: suppression menace, patching
5. Rétablissement: restaution propre, monitoring
6. Retour d'expérience: post-mortem dans 5 jours
        """
    },
]


def get_all_documents():
    """Retourne tous les documents de la base de connaissances"""
    return SECURITY_KNOWLEDGE


def get_documents_by_domain(domain: str):
    """Filtre par domaine"""
    return [d for d in SECURITY_KNOWLEDGE if d["domain"] in (domain, "general")]


def get_document_by_anomaly_type(anomaly_type: str):
    """Cherche un document par type d'anomalie"""
    at_lower = anomaly_type.lower().strip()
    for doc in SECURITY_KNOWLEDGE:
        if doc["anomaly_type"].lower() == at_lower:
            return doc
    for doc in SECURITY_KNOWLEDGE:
        if doc["anomaly_type"].lower() in at_lower or at_lower in doc["anomaly_type"].lower():
            return doc
    return None