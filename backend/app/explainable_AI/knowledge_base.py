import os
import re
from pathlib import Path
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

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
    # ========== NEW FIREWALL ENTRIES (20) ==========
    {
        "id": "fw_dns_exfil_001",
        "domain": "firewall",
        "anomaly_type": "Exfiltration DNS",
        "content": """
        Description : Détournement DNS pour exfiltration de données bancaires.
        Indicateurs : Requêtes TXT/AAAA inhabituelles, entropie élevée (>4.5), volume UDP/53 suspect.
        Causes : Malware exfiltrant des numéros de cartes ou soldes.
        Corrélations : Pics de lecture DB, processus inconnu sur OS.
        Actions : Bloquer domaine/IP source, isolation hôte. Remédiation : Nettoyage malware.
        Prévention : Filtrage DNSSEC, inspection Layer 7. Criticité : High.
        MITRE : T1071.004 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_vpn_bypass_001",
        "domain": "firewall",
        "anomaly_type": "Bypass VPN/SSH",
        "content": """
        Description : Tunneling non autorisé vers l'extérieur (SSH/VPN).
        Indicateurs : Sessions TCP longues sur 443/80 avec pattern binaire non-HTTP.
        Causes : Shadow IT, évitement des contrôles de sécurité, exfiltration.
        Actions : Couper session, analyse forensique de la machine. Remédiation : Proxy obligatoire.
        Prévention : SSL Deep Inspection, restriction ports sortants. Criticité : High.
        MITRE : T1572 | ISO 27001 : A.13.1.2 | NIST : PR.PT-4
        """
    },
    {
        "id": "fw_pci_violation_001",
        "domain": "firewall",
        "anomaly_type": "Violation Zone PCI-DSS",
        "content": """
        Description : Flux non autorisé vers la zone de données porteurs (CDE).
        Indicateurs : Logs de rejet (Deny) massifs entre DMZ et Zone Sécurisée.
        Causes : Erreur config, mouvement latéral d'un attaquant.
        Actions : Bloquer flux, alerter responsable conformité. Remédiation : Durcir segmentation.
        Prévention : Micro-segmentation, politique Zero Trust. Criticité : Critical.
        MITRE : T1083 | ISO 27001 : A.13.1.3 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_admin_brute_001",
        "domain": "firewall",
        "anomaly_type": "Brute force Admin FW",
        "content": """
        Description : Tentatives répétées de connexion sur l'interface admin du firewall.
        Indicateurs : >20 échecs de login en 1 min sur l'IP du FW.
        Causes : Attaque externe ou compromission interne.
        Actions : Bloquer IP source, changer mots de passe admin. Remédiation : MFA admin.
        Prévention : Accès admin via VPN/Bastion uniquement. Criticité : Critical.
        MITRE : T1110 | ISO 27001 : A.9.4.3 | NIST : PR.AC-7
        """
    },
    {
        "id": "fw_rule_drift_001",
        "domain": "firewall",
        "anomaly_type": "Dérive de règle (Drift)",
        "content": """
        Description : Modification non planifiée de la politique de sécurité du FW.
        Indicateurs : Changement de hash de config sans ticket de changement (RFC).
        Causes : Action interne malveillante ou erreur admin.
        Actions : Rollback config, auditer modification. Remédiation : Processus Change Mgmt.
        Prévention : Configuration as Code, outils d'audit continu. Criticité : High.
        MITRE : T1562.004 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "fw_geo_block_001",
        "domain": "firewall",
        "anomaly_type": "Trafic Géo-bloqué",
        "content": """
        Description : Communication avec une IP localisée dans un pays sous embargo.
        Indicateurs : Flux TCP réussi vers pays blacklisté (ex: NK, IR).
        Causes : Infection APT, erreur de routage.
        Actions : Couper trafic, isoler machine. Remédiation : Analyse malware.
        Prévention : Geofencing strict, Threat Intelligence. Criticité : High.
        MITRE : T1071 | ISO 27001 : A.13.1.1 | NIST : DE.AE-2
        """
    },
    {
        "id": "fw_c2_beacon_001",
        "domain": "firewall",
        "anomaly_type": "Beaconing C2",
        "content": """
        Description : Signal régulier vers un serveur de commande (C2).
        Indicateurs : Requêtes périodiques (jitter < 10%), même taille de payload.
        Causes : Infection botnet/RAT bancaire (ex: Qakbot).
        Actions : Isoler hôte, capture réseau PCAP. Remédiation : Nettoyage machine.
        Prévention : IDS/IPS avec signatures C2, Proxy filtrant. Criticité : Critical.
        MITRE : T1071.001 | ISO 27001 : A.12.2.1 | NIST : DE.CM-1
        """
    },
    {
        "id": "fw_ip_spoof_001",
        "domain": "firewall",
        "anomaly_type": "Spoofing IP Interne",
        "content": """
        Description : Paquet avec IP interne arrivant sur l'interface externe (WAN).
        Indicateurs : IP source du subnet LAN sur interface Internet.
        Causes : Attaque par rebond, tentative de bypass FW.
        Actions : Bloquer paquet, vérifier routeur amont. Remédiation : Anti-spoofing uRPF.
        Prévention : Règles de filtrage d'entrée (Ingress filtering). Criticité : High.
        MITRE : T1583 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_icmp_smurf_001",
        "domain": "firewall",
        "anomaly_type": "Flood ICMP (Smurf)",
        "content": """
        Description : Attaque par amplification ICMP saturant la bande passante.
        Indicateurs : Volume ICMP Echo Request massif vers adresse broadcast.
        Causes : DDoS volumétrique.
        Actions : Rate-limiting ICMP, blocage IP source. Remédiation : ISP scrubbing.
        Prévention : Désactiver broadcast ICMP sur routeurs. Criticité : Medium.
        MITRE : T1498 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "fw_ip_frag_001",
        "domain": "firewall",
        "anomaly_type": "Fragmentation IP suspecte",
        "content": """
        Description : Utilisation de fragments IP pour bypass l'inspection d'état (Stateful).
        Indicateurs : Taux de fragmentation anormal, offsets se chevauchant.
        Causes : Tentative d'IDS evasion (Teardrop).
        Actions : Dropper paquets fragmentés anormaux. Remédiation : Assemblage CPU FW.
        Prévention : Inspection minutieuse des fragments IP. Criticité : High.
        MITRE : T1203 | ISO 27001 : A.13.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "fw_ipv6_tunnel_001",
        "domain": "firewall",
        "anomaly_type": "Tunneling IPv6",
        "content": """
        Description : Encapsulation IPv6 dans IPv4 pour contourner les règles IPv4-only.
        Indicateurs : Protocole 41 (6to4) sur firewall non configuré pour.
        Causes : Bypass de filtrage, malware utilisant IPv6.
        Actions : Désactiver protocole 41, auditer machine. Remédiation : Config Dual Stack sécurisée.
        Prévention : Blocage des tunnels non autorisés. Criticité : High.
        MITRE : T1071 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_ssl_error_001",
        "domain": "firewall",
        "anomaly_type": "Échec Inspection SSL",
        "content": """
        Description : Flux HTTPS impossible à déchiffrer par le FW (certificat épinglé).
        Indicateurs : Alerte 'SSL Inspection Failed', certificat inconnu.
        Causes : Malware utilisant du chiffrement custom ou bypass d'inspection.
        Actions : Bloquer flux non inspectable, vérifier host. Remédiation : Politique SSL stricte.
        Prévention : Certificats racines contrôlés. Criticité : Medium.
        MITRE : T1573 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "fw_proto_anom_001",
        "domain": "firewall",
        "anomaly_type": "Anomalie Protocole HTTP",
        "content": """
        Description : Trafic binaire ou non-HTTP sur port 80/443.
        Indicateurs : Erreur parsing HTTP, signatures SSH/RDP dans flux port 80.
        Causes : Tunneling C2, contournement proxy.
        Actions : Couper flux, alerte système. Remédiation : Filtrage applicatif strict.
        Prévention : DPI Layer 7 obligatoire. Criticité : High.
        MITRE : T1071 | ISO 27001 : A.13.1.2 | NIST : PR.PT-4
        """
    },
    {
        "id": "fw_exfil_vol_001",
        "domain": "firewall",
        "anomaly_type": "Volume Exfiltration",
        "content": """
        Description : Transfert massif de données vers une destination externe inconnue.
        Indicateurs : Sortie > 5GB en 1h vers une IP inhabituelle.
        Causes : Vol de base de données clients ou logs.
        Actions : Suspendre flux machine, incident P1. Remédiation : Audit DLP.
        Prévention : Analyse de seuils adaptatifs, DLP réseau. Criticité : Critical.
        MITRE : T1020 | ISO 27001 : A.18.1.1 | NIST : PR.DS-5
        """
    },
    {
        "id": "fw_recon_denied_001",
        "domain": "firewall",
        "anomaly_type": "Taux Rejets Reconn",
        "content": """
        Description : Nombre élevé de connexions refusées depuis une seule source.
        Indicateurs : >100 blocks/min vers différents ports internes.
        Causes : Scan réseau ciblé, reconnaissance active.
        Actions : Ban IP source automatique, vérifier logs application. Remédiation : IPS actif.
        Prévention : Blocage automatique des scanners. Criticité : Medium.
        MITRE : T1595 | ISO 27001 : A.12.6.1 | NIST : DE.AE-2
        """
    },
    {
        "id": "fw_lat_move_fw_001",
        "domain": "firewall",
        "anomaly_type": "Mouvement Latéral FW",
        "content": """
        Description : Tentative de flux entre serveurs d'un même VLAN bloqué par FW interne.
        Indicateurs : Logs Deny entre Host_A et Host_B (même zone).
        Causes : Propagation de ver ou attaquant cherchant des cibles internes.
        Actions : Isoler Host_A, scan malware Host_B. Remédiation : Micro-segmentation.
        Prévention : Host-based Firewall (EDR). Criticité : High.
        MITRE : T1021 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_cloud_bridge_001",
        "domain": "firewall",
        "anomaly_type": "Pont Cloud non autorisé",
        "content": """
        Description : Connexion VPN/DirectConnect vers un tenant Cloud inconnu.
        Indicateurs : Nouveau peering réseau détecté sans autorisation.
        Causes : Shadow IT, exfiltration Cloud.
        Actions : Désactiver peering, identifier responsable. Remédiation : Gouvernance Cloud.
        Prévention : Contrôle des passerelles hybrides. Criticité : High.
        MITRE : T1583.003 | ISO 27001 : A.13.1.2 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_heartbleed_001",
        "domain": "firewall",
        "anomaly_type": "Exploit SSL (Heartbleed)",
        "content": """
        Description : Tentative d'exploitation de vulnérabilité OpenSSL.
        Indicateurs : Signature IPS 'Heartbleed attempt' détectée.
        Causes : Scan de vulnérabilités externe ou exploit ciblé.
        Actions : Vérifier version lib sur cible, patch. Remédiation : Upgrade OpenSSL.
        Prévention : Patch management régulier. Criticité : High.
        MITRE : T1210 | ISO 27001 : A.12.6.1 | NIST : PR.IP-12
        """
    },
    {
        "id": "fw_tor_traffic_001",
        "domain": "firewall",
        "anomaly_type": "Trafic Noeud TOR",
        "content": """
        Description : Communication avec un noeud de sortie/entrée TOR connu.
        Indicateurs : IP source/dest présente dans la liste publique des noeuds TOR.
        Causes : Employé contournant filtrage, C2 furtif.
        Actions : Bloquer IP, investiguer machine interne. Remédiation : Interdiction TOR.
        Prévention : Flux de Threat Intelligence actif. Criticité : High.
        MITRE : T1090.003 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "fw_smtp_bulk_001",
        "domain": "firewall",
        "anomaly_type": "Envoi Mail Massif",
        "content": """
        Description : Flux sortant SMTP (port 25) volumineux depuis un serveur non-mail.
        Indicateurs : >500 connexions SMTP/min depuis un serveur App.
        Causes : Serveur compromis servant de relais spam/phishing.
        Actions : Bloquer port 25 pour cet hôte, nettoyer machine. Remédiation : Relais SMTP interne.
        Prévention : Sortie SMTP autorisée uniquement pour passerelles mails. Criticité : High.
        MITRE : T1565 | ISO 27001 : A.13.1.1 | NIST : DE.CM-1
        """
    },

    # ========== NEW OS ENTRIES (20) ==========
    {
        "id": "os_root_esc_001",
        "domain": "os",
        "anomaly_type": "Éscalade Root",
        "content": """
        Description : Utilisateur non-privilégié obtenant des droits root/SYSTEM.
        Indicateurs : Appel système setuid, spawn shell root depuis processus app.
        Causes : Exploit kernel, mauvaise config sudo.
        Actions : Kill process, verrouiller compte, investiguer. Remédiation : Patching kernel.
        Prévention : Least privilege, durcissement SELinux. Criticité : Critical.
        MITRE : T1068 | ISO 27001 : A.9.2.3 | NIST : PR.AC-4
        """
    },
    {
        "id": "os_shadow_tamper_001",
        "domain": "os",
        "anomaly_type": "Altération /etc/shadow",
        "content": """
        Description : Modification non identifiée du fichier des mots de passe.
        Indicateurs : Alerte FIM sur /etc/shadow ou Registry SAM/SECURITY.
        Causes : Création backdoor, changement de hash admin.
        Actions : Vérifier intégrité, comparer avec backup. Remédiation : Reset hash.
        Prévention : FIM (File Integrity Monitoring) temps réel. Criticité : Critical.
        MITRE : T1003.008 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "os_kernel_expl_001",
        "domain": "os",
        "anomaly_type": "Exploit Kernel",
        "content": """
        Description : Utilisation d'un exploit pour compromettre le noyau OS.
        Indicateurs : Crash system répété suivi d'une exécution de code suspecte.
        Causes : Zero-day ou vulnérabilité non patchée.
        Actions : Reboot safe mode, analyse forensique. Remédiation : Mise à jour OS.
        Prévention : Patch management hebdomadaire. Criticité : Critical.
        MITRE : T1068 | ISO 27001 : A.12.6.1 | NIST : PR.IP-12
        """
    },
    {
        "id": "os_cron_persist_001",
        "domain": "os",
        "anomaly_type": "Persistance Cron",
        "content": """
        Description : Ajout d'une tâche planifiée suspecte pour exécution récurrente.
        Indicateurs : Nouveau fichier dans /etc/cron.d ou tâche Schtasks par compte Web.
        Causes : Backdoor, agent de surveillance malveillant.
        Actions : Supprimer tâche, analyser binaire cible. Remédiation : Purge host.
        Prévention : Audit des tâches planifiées. Criticité : High.
        MITRE : T1053.003 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "os_rootkit_bin_001",
        "domain": "os",
        "anomaly_type": "Rootkit Binaire",
        "content": """
        Description : Remplacement de binaires système (ls, ps, netstat) par des versions malveillantes.
        Indicateurs : Taille binaire incohérente, hash modifié sur binaires /bin.
        Causes : Installation de rootkit suite à intrusion.
        Actions : Isoler machine, réinstaller OS depuis source sûre. Remédiation : Full Wipe.
        Prévention : BIOS/UEFI Secure Boot, FIM. Criticité : Critical.
        MITRE : T1014 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "os_admin_off_001",
        "domain": "os",
        "anomaly_type": "Login Admin hors-heures",
        "content": """
        Description : Connexion privilégiée réussie à 3h du matin sans RFC associée.
        Indicateurs : EventID 4624 (Windows) ou SSH session (Linux) en horaire atypique.
        Causes : Attaquant utilisant des identifiants volés.
        Actions : Appeler admin pour confirmer, révoquer session si doute. Remédiation : MFA systématique.
        Prévention : Restriction horaire des connexions admin. Criticité : High.
        MITRE : T1078 | ISO 27001 : A.9.4.2 | NIST : DE.AE-3
        """
    },
    {
        "id": "os_lsass_dump_001",
        "domain": "os",
        "anomaly_type": "Dumping LSASS",
        "content": """
        Description : Tentative d'accès mémoire au processus LSASS pour extraire des hash/mots de passe.
        Indicateurs : Processus suspect accédant à lsass.exe (ex: procxdump, mimikatz).
        Causes : Etape critique de vol d'identifiants (Pass-the-Hash).
        Actions : Isoler machine, réinitialiser tous les mots de passe du host. Remédiation : Credential Guard.
        Prévention : EDR avec détection injection mémoire. Criticité : Critical.
        MITRE : T1003.001 | ISO 27001 : A.9.4.4 | NIST : PR.AC-1
        """
    },
    {
        "id": "os_log_clear_001",
        "domain": "os",
        "anomaly_type": "Effacement de Logs",
        "content": """
        Description : Suppression volontaire des journaux d'événements.
        Indicateurs : Commande 'wevtutil cl' ou arrêt brutal du service syslog.
        Causes : Attaquant masquant ses traces post-intrusion.
        Actions : Incident P1, vérifier logs SIEM déportés. Remédiation : Analyse forensique.
        Prévention : Forwarding logs temps réel sur serveur distant. Criticité : High.
        MITRE : T1070.001 | ISO 27001 : A.12.4.2 | NIST : PR.PT-1
        """
    },
    {
        "id": "os_unauth_mount_001",
        "domain": "os",
        "anomaly_type": "Montage Partition Suspect",
        "content": """
        Description : Montage d'un volume USB ou d'un partage réseau non habituel.
        Indicateurs : EventID 4663 (Accès objet) ou log mount sur /mnt.
        Causes : Exfiltration physique de données ou ajout d'outils d'attaque.
        Actions : Bloquer montage, identifier utilisateur. Remédiation : Désactivation USB.
        Prévention : Contrôle des périphériques (Device Control). Criticité : Medium.
        MITRE : T1052 | ISO 27001 : A.8.3.1 | NIST : PR.PT-2
        """
    },
    {
        "id": "os_obfusc_pwrshell_001",
        "domain": "os",
        "anomaly_type": "PowerShell Obfusqué",
        "content": """
        Description : Exécution de commandes PowerShell encodées en Base64/XOR.
        Indicateurs : Processus powershell.exe avec arguments '-Enc' ou longs strings aléatoires.
        Causes : Script malveillant d'intrusion ou de reconnaissance.
        Actions : Kill process, décoder commande, investiguer. Remédiation : Signature scripts.
        Prévention : Restreindre PowerShell (Constrained Language Mode). Criticité : High.
        MITRE : T1059.001 | ISO 27001 : A.12.1.2 | NIST : DE.CM-1
        """
    },
    {
        "id": "os_orphan_proc_001",
        "domain": "os",
        "anomaly_type": "Processus Orphelin Suspect",
        "content": """
        Description : Processus tournant sans parent légitime (init as parent).
        Indicateurs : PPID=1 pour un processus n'étant pas un daemon connu.
        Causes : Technique d'évasion pour cacher un agent malveillant.
        Actions : Inspecter arborescence processus, hash binaire. Remédiation : Suspendre process.
        Prévention : Monitoring de l'arbre des processus (Process Tree). Criticité : Medium.
        MITRE : T1055 | ISO 27001 : A.12.1.2 | NIST : DE.AE-2
        """
    },
    {
        "id": "os_syslog_tamper_001",
        "domain": "os",
        "anomaly_type": "Altération Config Syslog",
        "content": """
        Description : Modification de la destination des logs dans /etc/syslog.conf.
        Indicateurs : Alerte FIM sur fichiers de config logging.
        Causes : Désactivation du forwarding SIEM par un intrus.
        Actions : Restaurer config, vérifier SIEM. Remédiation : Durcir config audit.
        Prévention : FIM on folders /etc. Criticité : High.
        MITRE : T1562.001 | ISO 27001 : A.12.4.2 | NIST : PR.PT-1
        """
    },
    {
        "id": "os_low_port_001",
        "domain": "os",
        "anomaly_type": "Port Écoute Bas",
        "content": """
        Description : Ouverture d'un port < 1024 par un processus utilisateur non-root.
        Indicateurs : 'netstat -plunt' montrant application web écoutant sur port root.
        Causes : Mauvaise configuration ou exploit facilitant l'accès.
        Actions : Identifier processus, revoir permissions. Remédiation : Cap_net_bind_service.
        Prévention : Utilisation de privilèges restreints (Linux Capabilities). Criticité : Medium.
        MITRE : T1567 | ISO 27001 : A.12.1.2 | NIST : PR.AC-4
        """
    },
    {
        "id": "os_fake_ca_001",
        "domain": "os",
        "anomaly_type": "Injection CA / Certificat",
        "content": """
        Description : Installation d'un nouveau certificat racine (Root CA) non approuvé.
        Indicateurs : Modification du store de certificats OS (Trusted Root).
        Causes : Préparation d'une attaque Man-in-the-Middle (MitM).
        Actions : Supprimer certificat, vérifier origine. Remédiation : Lockdown cert store.
        Prévention : Contrôle d'intégrité du magasin de certificats. Criticité : High.
        MITRE : T1553.004 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "os_raw_disk_001",
        "domain": "os",
        "anomaly_type": "Accès Disque Direct",
        "content": """
        Description : Processus lisant directement le disque physique (bypass filesystem).
        Indicateurs : Accès à \\.\PhysicalDrive (Windows) ou /dev/sdX par app non-admin.
        Causes : Lecture de secrets, bypass de contrôles de sécurité.
        Actions : Kill process, analyser machine. Remédiation : Durcissement accès hardware.
        Prévention : EDR alertant sur les accès disque Raw. Criticité : High.
        MITRE : T1006 | ISO 27001 : A.12.1.2 | NIST : PR.AC-3
        """
    },
    {
        "id": "os_net_cfg_tamper_001",
        "domain": "os",
        "anomaly_type": "Altération Config Réseau",
        "content": """
        Description : Changement des serveurs DNS ou de la passerelle par défaut.
        Indicateurs : Modification DNS dans /etc/resolv.conf ou Registre Interfaces.
        Causes : Détournement de trafic vers proxy malveillant (MitM).
        Actions : Restaurer config réseau, vérifier intégrité OS. Remédiation : DHCP sécurisé.
        Prévention : Verrouillage des paramètres réseau. Criticité : High.
        MITRE : T1562.004 | ISO 27001 : A.13.1.2 | NIST : PR.AC-5
        """
    },
    {
        "id": "os_av_edr_kill_001",
        "domain": "os",
        "anomaly_type": "Désactivation Agent Sécurité",
        "content": """
        Description : Arrêt brutal ou désinstallation de l'antivirus / EDR.
        Indicateurs : Service 'WinDefend' ou agent 'CrowdStrike' arrêté.
        Causes : Attaquant préparant le chiffrement ou l'exfiltration.
        Actions : Isoler machine manuellement (isolation physique), réinstaller agent. Remédiation : Incident P1.
        Prévention : Protection anti-tamper activée. Criticité : Critical.
        MITRE : T1562.001 | ISO 27001 : A.12.2.1 | NIST : DE.CM-1
        """
    },
    {
        "id": "os_sudo_abuse_001",
        "domain": "os",
        "anomaly_type": "Abus de Sudo",
        "content": """
        Description : Utilisation excessive ou inhabituelle de la commande sudo.
        Indicateurs : >50 commandes sudo en 5 min par un compte service.
        Causes : Script d'automatisation mal écrit ou attaquant en escalade.
        Actions : Auditer commandes passées, vérifier intégrité. Remédiation : Revoir sudoers.
        Prévention : Logging détaillé des entrées TTY (sudo -V). Criticité : Medium.
        MITRE : T1548.003 | ISO 27001 : A.9.2.3 | NIST : PR.AC-4
        """
    },
    {
        "id": "os_dll_inject_001",
        "domain": "os",
        "anomaly_type": "Injection DLL / SO",
        "content": """
        Description : Chargement d'une bibliothèque malveillante dans un processus légitime.
        Indicateurs : EventID 7 (DLL Load) avec path suspect (ex: Temp, Downloads).
        Causes : Elévation de privilèges ou vol de session applicative.
        Actions : Tuer processus infecté, analyser DLL. Remédiation : Code signing.
        Prévention : Windows AppLocker ou Linux Kernel Hardening. Criticité : High.
        MITRE : T1055.001 | ISO 27001 : A.14.2.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "os_temp_exec_001",
        "domain": "os",
        "anomaly_type": "Exécution depuis Temp",
        "content": """
        Description : Lancement d'un binaire depuis un répertoire temporaire.
        Indicateurs : Processus dont l'image se trouve dans /tmp ou AppData/Local/Temp.
        Causes : Comportement typique de dropper ou de malware de stade 1.
        Actions : Isoler host, supprimer fichier, analyser hash. Remédiation : Nettoyage auto.
        Prévention : Montage /tmp avec option noexec (Linux) ou SRP (Windows). Criticité : High.
        MITRE : T1204.002 | ISO 27001 : A.12.1.2 | NIST : PR.IP-12
        """
    },
    # ========== NEW APP ENTRIES (20) ==========
    {
        "id": "app_geo_travel_001",
        "domain": "app",
        "anomaly_type": "Voyage Impossible",
        "content": """
        Description : Accès au compte depuis deux pays distants en < 1h.
        Indicateurs : Login User_A Paris (14h), Login User_A Tokyo (14h15).
        Causes : Partage de compte, vol de session, botnet.
        Actions : Geler compte, invalider sessions, MFA obligatoire. Remédiation : Audit IP.
        Prévention : Géofencing applicatif. Criticité : High.
        MITRE : T1078 | ISO 27001 : A.9.4.2 | NIST : DE.AE-3
        """
    },
    {
        "id": "app_iban_mod_001",
        "domain": "app",
        "anomaly_type": "Fraude IBAN",
        "content": """
        Description : Modification massive d'IBAN bénéficiaires avant virements.
        Indicateurs : Pic d'appels sur /api/v1/profile/iban (>100/min).
        Causes : Attaque "Man-in-the-Browser" ou insider threat.
        Actions : Bloquer virements sortants, alerter fraude. Remédiation : Double validation.
        Prévention : Notification SMS pour tout changement IBAN. Criticité : Critical.
        MITRE : T1565.001 | ISO 27001 : A.14.2.1 | NIST : PR.DS-1
        """
    },
    {
        "id": "app_insider_pix_001",
        "domain": "app",
        "anomaly_type": "Accès Client Insider",
        "content": """
        Description : Employé consultant des dossiers clients sans lien avec ses tâches.
        Indicateurs : Accès à >50 comptes clients différents en 1h par un conseiller.
        Causes : Curiosité malveillante, préparation de fraude, vol de données.
        Actions : Suspension immédiate accès, audit RH. Remédiation : Procédure disciplinaire.
        Prévention : RBAC strict, audit logs d'accès nominatifs. Criticité : High.
        MITRE : T1078 | ISO 27001 : A.7.2.2 | NIST : PR.AT-1
        """
    },
    {
        "id": "app_xss_stored_001",
        "domain": "app",
        "anomaly_type": "XSS Stockée",
        "content": """
        Description : Injection de script malveillant dans un champ commentaire/profil.
        Indicateurs : Caractères <script> ou alert() détectés dans les logs applicatifs.
        Causes : Absence de sanitization des entrées utilisateur.
        Actions : Nettoyer DB, invalider entrées, patcher code. Remédiation : Trusted Types.
        Prévention : CSP (Content Security Policy) stricte. Criticité : High.
        MITRE : T1189 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_bulk_pdf_001",
        "domain": "app",
        "anomaly_type": "Exfil PDF Massif",
        "content": """
        Description : Téléchargement soudain de milliers de relevés bancaires.
        Indicateurs : Volume HTTP sortant anormalement élevé sur endpoints PDF.
        Causes : Script de scraping, exfiltration de PII.
        Actions : Bloquer ID utilisateur, vérifier logs IP. Remédiation : Rate-limit.
        Prévention : CAPTCHA sur téléchargements répétitifs. Criticité : High.
        MITRE : T1020 | ISO 27001 : A.13.1.1 | NIST : PR.DS-5
        """
    },
    {
        "id": "app_sess_fix_001",
        "domain": "app",
        "anomaly_type": "Session Fixation",
        "content": """
        Description : Utilisation d'un ID de session pré-défini pour usurper un compte.
        Indicateurs : Session ID identique avant et après authentification.
        Causes : Vulnérabilité dans la gestion des cookies de session.
        Actions : Invalider session, forcer re-login. Remédiation : Session regeneration.
        Prévention : Cookies Secure & HttpOnly. Criticité : High.
        MITRE : T1550 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "app_csrf_trans_001",
        "domain": "app",
        "anomaly_type": "CSRF Transaction",
        "content": """
        Description : Exécution d'un virement forcée via un site tiers malveillant.
        Indicateurs : Requête POST virement sans token CSRF valide.
        Causes : Absence de protection anti-CSRF sur les actions sensibles.
        Actions : Annuler transaction, auditer comptes impactés. Remédiation : SameSite cookies.
        Prévention : Tokens CSRF obligatoires, validation d'origine. Criticité : Critical.
        MITRE : T1566 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_idor_vert_001",
        "domain": "app",
        "anomaly_type": "IDOR Vertical",
        "content": """
        Description : Client accédant à des fonctions admin via manipulation URL.
        Indicateurs : Accès à /api/admin/* par un utilisateur 'role:user'.
        Causes : Contrôle d'accès broken au niveau fonctionnel.
        Actions : Bloquer utilisateur, patcher décorateurs d'auth. Remédiation : RBAC server-side.
        Prévention : Tests de sécurité unitaires sur les rôles. Criticité : High.
        MITRE : T1068 | ISO 27001 : A.9.2.3 | NIST : PR.AC-4
        """
    },
    {
        "id": "app_web_shell_001",
        "domain": "app",
        "anomaly_type": "Upload WebShell",
        "content": """
        Description : Téléchargement d'un script .php / .jsp capable d'exécuter des commandes.
        Indicateurs : Fichier avec double extension (ex: image.jpg.php) en zone upload.
        Causes : Absence de vérification du type MIME / extension.
        Actions : Supprimer fichier, isoler serveur, analyse forensique. Remédiation : Scan AV upload.
        Prévention : Renommage fichiers uploadés, stockage hors document root. Criticité : Critical.
        MITRE : T1505.003 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "app_debug_page_001",
        "domain": "app",
        "anomaly_type": "Accès Page Debug",
        "content": """
        Description : Exposition d'interfaces de diagnostic en production.
        Indicateurs : Visites sur /phpinfo, /debug, /actuator/env.
        Causes : Mauvaise configuration de déploiement (debug: true).
        Actions : Désactiver endpoints, changer secrets exposés. Remédiation : Config hardening.
        Prévention : Pipeline CI/CD vérifiant les flags de prod. Criticité : Medium.
        MITRE : T1592 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "app_ransom_app_001",
        "domain": "app",
        "anomaly_type": "Ransomware Applicatif",
        "content": """
        Description : Chiffrement des données stockées via l'application.
        Indicateurs : Contenu DB ou fichiers user soudainement illisibles (hash binaire).
        Causes : Compromission de clé de chiffrement applicative.
        Actions : Couper app, isoler DB, incident cyber majeur. Remédiation : Disaster Recovery.
        Prévention : Gestion sécurisée des clés (HSM/KMS). Criticité : Critical.
        MITRE : T1486 | ISO 27001 : A.17.1.1 | NIST : RS.RP-1
        """
    },
    {
        "id": "app_l7_dos_001",
        "domain": "app",
        "anomaly_type": "DDoS Layer 7",
        "content": """
        Description : Inondation de requêtes HTTP legitimation consommant CPU/RAM.
        Indicateurs : Pic de requêtes 200 OK multiplié par 50 sans campagne marketing.
        Causes : Botnet simulant navigation humaine.
        Actions : Activer WAF JS challenge, filtrage IP. Remédiation : Auto-scaling.
        Prévention : Rate-limiting par IP/Session. Criticité : High.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_err_leak_001",
        "domain": "app",
        "anomaly_type": "Fuite Infos Erreur",
        "content": """
        Description : Messages d'erreur révélant versions logicielles ou structure DB.
        Indicateurs : Stacktrace Java/Python affiché à l'utilisateur final.
        Causes : Gestionnaire d'exception trop verbeux.
        Actions : Masquer logs erreur, patcher code. Remédiation : Generic Error Pages.
        Prévention : Audit de logs applicatifs. Criticité : Low.
        MITRE : T1592 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "app_vuln_dep_001",
        "domain": "app",
        "anomaly_type": "Dépendance Vulnérable",
        "content": """
        Description : Utilisation d'une librairie avec CVE critique (ex: Log4j).
        Indicateurs : Alerte SCA (Software Composition Analysis) sur binaire déployé.
        Causes : Absence de mise à jour des dépendances.
        Actions : Identifier serveurs impactés, patcher immediatement. Remédiation : Upgrade version.
        Prévention : Pipeline DevSecOps bloquant les CVE > 8.0. Criticité : High.
        MITRE : T1190 | ISO 27001 : A.12.6.1 | NIST : PR.IP-12
        """
    },
    {
        "id": "app_jwt_replay_001",
        "domain": "app",
        "anomaly_type": "Replay JWT",
        "content": """
        Description : Réutilisation d'un jeton dérobé pour accès non autorisé.
        Indicateurs : Utilisation d'un token dont la session a été fermée (logout).
        Causes : Absence de blacklist de jetons ou durée de vie trop longue (TTL).
        Actions : Invalider tous les tokens de l'utilisateur, forcer login. Remédiation : Refresh tokens.
        Prévention : Short-lived tokens, rotation de clés. Criticité : High.
        MITRE : T1550 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "app_clickjack_001",
        "domain": "app",
        "anomaly_type": "Clickjacking",
        "content": """
        Description : Détournement de clics via une iframe invisible sur site tiers.
        Indicateurs : Appels sensibles avec referer inconnu ou absence de X-Frame-Options.
        Causes : Site bancaire autorisé à être encadré par n'importe quel domaine.
        Actions : Ajouter headers sécu, informer clients. Remédiation : Content Security Policy.
        Prévention : Header X-Frame-Options: DENY. Criticité : Medium.
        MITRE : T1189 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_ssrf_cloud_001",
        "domain": "app",
        "anomaly_type": "SSRF Cloud Meta",
        "content": """
        Description : Forcer le serveur à appeler l'API de métadonnées Cloud (169.254.169.254).
        Indicateurs : Logs réseau montrant accès serveur vers IP meta Cloud.
        Causes : Endpoint acceptant une URL non filtrée en paramètre.
        Actions : Bloquer endpoint, révoquer rôles IAM serveur. Remédiation : Whitelist URL.
        Prévention : IMDSv2 (AWS) ou équivalent, network egress rules. Criticité : Critical.
        MITRE : T1557 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_unsafe_des_001",
        "domain": "app",
        "anomaly_type": "Désérialisation non sécu",
        "content": """
        Description : Exécution de code via objets sérialisés malveillants.
        Indicateurs : Appels Java RMI ou Python pickle avec données binaires suspectes.
        Causes : Confiance aveugle dans les données d'entrée sérialisées.
        Actions : Isoler serveur, patcher format d'échange. Remédiation : Utiliser JSON/XML sûr.
        Prévention : Ne jamais désérialiser des données provenant de l'extérieur. Criticité : Critical.
        MITRE : T1203 | ISO 27001 : A.14.2.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "app_otp_brute_001",
        "domain": "app",
        "anomaly_type": "Brute force OTP",
        "content": """
        Description : Tentatives répétées de deviner le code de validation SMS/Mail.
        Indicateurs : >5 échecs de validation OTP en 2 min pour un user_id.
        Causes : Script d'automatisation cherchant à valider un virement frauduleux.
        Actions : Bloquer virement, auditer IP, réinitialiser auth. Remédiation : Lock temporaire.
        Prévention : Rate-limiting strict sur le champ OTP. Criticité : High.
        MITRE : T1110 | ISO 27001 : A.9.4.3 | NIST : PR.AC-7
        """
    },
    {
        "id": "app_session_limit_001",
        "domain": "app",
        "anomaly_type": "Dépassement Limite Sess",
        "content": """
        Description : Un utilisateur ouvre >20 sessions simultanées depuis des IPs différentes.
        Indicateurs : Count(session_id) unique par user_id anormal.
        Causes : Botnet distribuant un compte compromis, attaque par force brute réussie.
        Actions : Invalider sessions, changer mot de passe. Remédiation : Session Limit policy.
        Prévention : Alerte sur session concurrente géographique. Criticité : High.
        MITRE : T1078 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },

    # ========== NEW API ENTRIES (20) ==========
    {
        "id": "api_bola_api1_001",
        "domain": "api",
        "anomaly_type": "Attaque BOLA (API1)",
        "content": """
        Description : Accès aux données d'autrui via manipulation d'ID (ex: /api/acc/101 -> 102).
        Indicateurs : Code 200 OK sur des ressources appartenant à d'autres UserIDs.
        Causes : Validation de propriété manquante en backend.
        Actions : Bloquer endpoint, auditer fuite. Remédiation : Owner check interceptor.
        Prévention : Utilisation de IDs non-prédictibles (UUID). Criticité : Critical.
        MITRE : T1592 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_weak_auth_001",
        "domain": "api",
        "anomaly_type": "Authentification API faible",
        "content": """
        Description : Clés API transmises en clair ou tokens statiques longue durée.
        Indicateurs : API Keys détectées dans les logs proxy ou URLs.
        Causes : Mauvaise implémentation du protocole d'échange sécurisé.
        Actions : Révoquer clés, forcer rotation. Remédiation : OAuth 2.0 / OIDC.
        Prévention : Scan de secrets dans le code source. Criticité : High.
        MITRE : T1550 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "api_data_leak_001",
        "domain": "api",
        "anomaly_type": "Exposition Données Exc",
        "content": """
        Description : L'API retourne des objets JSON entiers incluant des champs sensibles (ex: password_hash, PII).
        Indicateurs : Réponse API avec champs non nécessaires au client final.
        Causes : Sérialisation directe des modèles DB vers JSON (API3).
        Actions : Filtrer sorties API, patcher DTO. Remédiation : Data Transfer Objects.
        Prévention : Revue des schémas d'API (OpenAPI/Swagger). Criticité : Medium.
        MITRE : T1592 | ISO 27001 : A.18.1.1 | NIST : PR.DS-5
        """
    },
    {
        "id": "api_res_exhaust_001",
        "domain": "api",
        "anomaly_type": "Épuisement Ressources API",
        "content": """
        Description : Requêtes provoquant une surcharge serveur via objets imbriqués.
        Indicateurs : Requêtes GraphQL avec profondeur excessive ou JSON récursif.
        Causes : Absence de limites sur la taille/complexité des payloads (API4).
        Actions : Activer Timeout, revoir parsing JSON. Remédiation : Query complexity limiting.
        Prévention : Parser limits, rate-limit. Criticité : High.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_bfla_api5_001",
        "domain": "api",
        "anomaly_type": "Défaut Auth Fonction (BFLA)",
        "content": """
        Description : Accès à des fonctions administratives par des utilisateurs normaux via API.
        Indicateurs : Succès sur DELETE /api/admin/config par un compte user.
        Causes : Contrôle de privilèges manquant sur les méthodes HTTP (API5).
        Actions : Révoquer accès, auditer logs d'administration. Remédiation : Centralized AuthZ.
        Prévention : Tests de pénétration réguliers sur API. Criticité : High.
        MITRE : T1068 | ISO 27001 : A.9.2.3 | NIST : PR.AC-4
        """
    },
    {
        "id": "api_mass_assign_001",
        "domain": "api",
        "anomaly_type": "Mass Assignment",
        "content": """
        Description : Modification de champs protégés (ex: is_admin: true) via requête d'update profil.
        Indicateurs : Payload d'update incluant des champs non présents dans le formulaire UI.
        Causes : Mapping automatique de l'entrée vers l'objet DB sans whitelist (API6).
        Actions : Invalider modifications, patcher models. Remédiation : strict input validation.
        Prévention : Utilisation de DTOs dédiés par action. Criticité : High.
        MITRE : T1565 | ISO 27001 : A.14.2.1 | NIST : PR.DS-1
        """
    },
    {
        "id": "api_cors_lax_001",
        "domain": "api",
        "anomaly_type": "Politique CORS Laxiste",
        "content": """
        Description : Autorisation d'accès API depuis n'importe quel domaine (Access-Control-Allow-Origin: *).
        Indicateurs : Alerte de scan 'CORS wildcard found'.
        Causes : Configuration de développement laissée en production.
        Actions : Restreindre domaines autorisés, révoquer *. Remédiation : Fixed Whitelist.
        Prévention : Headers Security audit. Criticité : Medium.
        MITRE : T1189 | ISO 27001 : A.14.2.5 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_nosql_inj_001",
        "domain": "api",
        "anomaly_type": "Injection NoSQL",
        "content": """
        Description : Manipulation de filtres MongoDB/NoSQL via paramètres API.
        Indicateurs : Requêtes avec opérateurs {$ne: null} ou {$gt: ''} dans les paramètres.
        Causes : Concaténation de paramètres dans les requêtes NoSQL.
        Actions : Bloquer IP, auditer DB. Remédiation : Sanitize filters.
        Prévention : Utilisation de librairies ODM sécurisées. Criticité : Critical.
        MITRE : T1190 | ISO 27001 : A.14.2.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_shadow_v1_001",
        "domain": "api",
        "anomaly_type": "API Shadow / V1",
        "content": """
        Description : Trafic sur d'anciennes versions d'API non surveillées.
        Indicateurs : Logs de trafic sur /v1/ alors que la v2 est la seule officielle.
        Causes : Serveurs legacy non déprovisionnés (API9).
        Actions : Désactiver endpoints v1, router tout trafic vers v2. Remédiation : Decommissioning.
        Prévention : API Gateway avec catalogue d'API strict. Criticité : Medium.
        MITRE : T1583 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "api_massive_401_001",
        "domain": "api",
        "anomaly_type": "Enumération Auth API",
        "content": """
        Description : Taux anormal d'erreurs 401/403 suggérant un scan.
        Indicateurs : Un seul IP générant >500 erreurs 401 en 1 minute.
        Causes : Tentative de découverte de credentials ou de clés API.
        Actions : Ban IP temporaire, alerte SIEM. Remédiation : IP Throttling.
        Prévention : Monitoring des codes retour HTTP. Criticité : Medium.
        MITRE : T1110 | ISO 27001 : A.12.6.1 | NIST : DE.AE-2
        """
    },
    {
        "id": "api_key_url_001",
        "domain": "api",
        "anomaly_type": "API Key dans URL",
        "content": """
        Description : Clé secrète transmise en paramètre de requête GET.
        Indicateurs : URL de type /api/data?key=ABCDEF12345 dans les logs.
        Causes : Mauvais design d'authentification, fuite dans les logs proxy/browser history.
        Actions : Révoquer clé, migrer vers Authorization Header. Remédiation : Bearer tokens.
        Prévention : Analyse statique de code (SAST). Criticité : High.
        MITRE : T1550 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "api_xxe_pay_001",
        "domain": "api",
        "anomaly_type": "XXE API XML",
        "content": """
        Description : Injection d'entités externes dans un payload XML API.
        Indicateurs : Requête XML avec <!ENTITY system 'file:///etc/passwd'>.
        Causes : Parser XML n'ayant pas désactivé les entités externes.
        Actions : Isoler serveur, patcher parser XML. Remédiation : Disable DTD.
        Prévention : Utilisation de JSON par défaut. Criticité : Critical.
        MITRE : T1190 | ISO 27001 : A.14.2.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_cred_stuff_001",
        "domain": "api",
        "anomaly_type": "Credential Stuffing API",
        "content": """
        Description : Tentative massive de login utilisant des bases de données fuitées.
        Indicateurs : Pic d'échecs login (>1000/min) avec des usernames variés depuis IPs variées (botnet).
        Causes : Attaque automatisée suite à un leak externe.
        Actions : Activer CAPTCHA, réinitialisation de passwords forcée sur comptes à risque. Remédiation : WAF protection.
        Prévention : Monitoring de la compromission de credentials externe (HIBP). Criticité : Critical.
        MITRE : T1110.004 | ISO 27001 : A.9.4.3 | NIST : PR.AC-7
        """
    },
    {
        "id": "api_casc_fail_001",
        "domain": "api",
        "anomaly_type": "Échec en Cascade API",
        "content": """
        Description : Un microservice lent ralentissant toute la chaîne d'appel.
        Indicateurs : Temps de réponse global x10, erreurs 504 Timeout généralisées.
        Causes : Absence de circuit breaker ou congestion réseau.
        Actions : Identifier service lent, reboot, activer mode dégradé. Remédiation : Circuit Breaker implementation.
        Prévention : Healthcheck actifs, quotas inter-services. Criticité : Medium.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_res_size_001",
        "domain": "api",
        "anomaly_type": "Oracle Taille Réponse",
        "content": """
        Description : Déduction d'infos via variations de taille des réponses API.
        Indicateurs : Différence systématique de taille entre 'User non trouvé' et 'Password faux'.
        Causes : Messages d'erreur trop spécifiques ou payloads variables.
        Actions : Harmoniser réponses, patcher logs. Remédiation : Unified Error Response.
        Prévention : Security testing for side-channels. Criticité : Low.
        MITRE : T1592 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "api_proto_down_001",
        "domain": "api",
        "anomaly_type": "Fallback Protocol API",
        "content": """
        Description : Forcer l'API à utiliser un protocole moins sûr (ex: HTTP, TLS 1.0).
        Indicateurs : Augmentation soudaine du trafic sur port 80 non redirigé.
        Causes : Attaque MitM cherchant à intercepter des tokens bancaires.
        Actions : Désactiver protocols legacy, forcer HSTS (Strict Transport Security). Remédiation : TLS Policy update.
        Prévention : Minimum TLS 1.2, certificat pinning. Criticité : High.
        MITRE : T1557 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "api_payload_bypass_001",
        "domain": "api",
        "anomaly_type": "Bypass Taille Payload",
        "content": """
        Description : Envoi de fichiers/JSON gigantesques pour saturer la RAM.
        Indicateurs : Requêtes HTTP avec Content-Length > 100MB sur endpoints textes.
        Causes : Absence de vérification des limites de taille en amont de la Gateway.
        Actions : Tuer session, appliquer limite stricte sur Nginx/API Gateway. Remédiation : Request size limit.
        Prévention : Configuration infrastructurelle de sécurité. Criticité : Medium.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_path_trav_001",
        "domain": "api",
        "anomaly_type": "Path Traversal API",
        "content": """
        Description : Tentative de lecture de fichiers via paramètres de chemin (ex: file=../../etc/passwd).
        Indicateurs : Caractères '../' ou '%2e%2e%2f' dans les paramètres de requêtes API.
        Causes : Paramétrage de fichiers non sécurisé en backend.
        Actions : Bloquer utilisateur, auditer accès filesystem. Remédiation : Path normalization.
        Prévention : Liste blanche de fichiers autorisés. Criticité : Critical.
        MITRE : T1190 | ISO 27001 : A.13.1.2 | NIST : PR.PT-4
        """
    },
    {
        "id": "api_key_share_001",
        "domain": "api",
        "anomaly_type": "Partage Clé API",
        "content": """
        Description : Une clé API unique utilisée depuis des localisations géographiques distantes en même temps.
        Indicateurs : API_KEY_X utilisée par IP_Paris et IP_Bangkok simultanément.
        Causes : Clé fuitée ou partagée entre partenaires non autorisés.
        Actions : Révoquer clé, contacter propriétaire. Remédiation : Key rotation policy.
        Prévention : IP binding pour les clés API critiques. Criticité : High.
        MITRE : T1550 | ISO 27001 : A.9.4.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "api_batch_abuse_001",
        "domain": "api",
        "anomaly_type": "Abus d'Opé Batch",
        "content": """
        Description : Utilisation des fonctions de batch pour exfiltrer des données massivement sans déclencher d'alerte par appel unitaire.
        Indicateurs : Requête /api/batch avec >1000 opérations de lecture.
        Causes : Absence de limite sur le nombre d'opérations dans un seul appel.
        Actions : Bloquer transaction, réduire limite de batch. Remédiation : Batch size enforcement.
        Prévention : Audit spécifique sur les endpoints d'agrégation. Criticité : High.
        MITRE : T1020 | ISO 27001 : A.13.1.1 | NIST : PR.DS-5
        """
    },
    # ========== NEW DATABASE ENTRIES (20) ==========
    {
        "id": "db_sqli_time_001",
        "domain": "db",
        "anomaly_type": "SQLI Time-based",
        "content": """
        Description : Injection SQL provoquant des délais d'attente (SLEEP).
        Indicateurs : Requêtes prenant >10s de manière répétée sur un seul champ.
        Causes : Paramètre URL non filtré permettant l'aveugle (Blind SQLi).
        Actions : Bloquer IP, analyser backend, patcher code. Remédiation : Prepared Statements.
        Prévention : Utilisation d'ORM sécurisé, scanner de vulnérabilités. Criticité : Critical.
        MITRE : T1190 | ISO 27001 : A.14.2.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "db_massive_export_001",
        "domain": "db",
        "anomaly_type": "Export Table Massif",
        "content": """
        Description : Extraction de l'intégralité d'une table sensible (Comptes).
        Indicateurs : SELECT * sans clause WHERE sur table > 1M lignes.
        Causes : Tentative de vol de base de données par un admin ou malware.
        Actions : Tuer transaction, révoquer user, incident P1. Remédiation : Audit logs.
        Prévention : Quotas de lignes par requête, masquage de données. Criticité : Critical.
        MITRE : T1537 | ISO 27001 : A.18.1.1 | NIST : PR.DS-5
        """
    },
    {
        "id": "db_priv_user_001",
        "domain": "db",
        "anomaly_type": "Création User Priv",
        "content": """
        Description : Nouvel utilisateur DB avec droits 'SUPER' ou 'dba'.
        Indicateurs : Commande 'CREATE USER' suivie de 'GRANT ALL'.
        Causes : Préparation d'une persistance par un attaquant.
        Actions : Supprimer utilisateur, vérifier login d'origine. Remédiation : Audit privilèges.
        Prévention : IAM coordonné, alertes sur modification de droits. Criticité : High.
        MITRE : T1078.002 | ISO 27001 : A.9.2.2 | NIST : PR.AC-2
        """
    },
    {
        "id": "db_schema_drift_001",
        "domain": "db",
        "anomaly_type": "Dérive Schéma DB",
        "content": """
        Description : Modification de la structure des tables (DROP/ALTER) hors maintenance.
        Indicateurs : EventID 'DDL Statement' détecté sur table de production.
        Causes : Sabotage ou erreur humaine critique.
        Actions : Rollback schéma, analyser utilisateur responsable. Remédiation : Change management.
        Prévention : Droits DDL restreints en production. Criticité : High.
        MITRE : T1565.001 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "db_ip_bypass_001",
        "domain": "db",
        "anomaly_type": "Bypass IP Backend",
        "content": """
        Description : Connexion DB depuis une IP n'appartenant pas au pool App.
        Indicateurs : IP source inconnue dans les logs pg_hba (Postgres) / SQL Audit.
        Causes : Accès direct par un admin ou attaquant ayant pivoté.
        Actions : Couper connexion, vérifier bastion. Remédiation : Whitelist IP stricte.
        Prévention : Segmentation réseau VLAN DB. Criticité : Critical.
        MITRE : T1078 | ISO 27001 : A.13.1.3 | NIST : PR.AC-3
        """
    },
    {
        "id": "db_bruteforce_001",
        "domain": "db",
        "anomaly_type": "Brute force DB",
        "content": """
        Description : Multiples échecs de connexion sur le compte 'sa' ou 'postgres'.
        Indicateurs : >100 échecs de connexion en 1 min.
        Causes : Script de brute force interne ou externe (si exposé).
        Actions : Bannir IP source, vérifier exposition port 5432/3306. Remédiation : Password policy.
        Prévention : Fail2Ban sur logs DB, pas d'exposition publique. Criticité : High.
        MITRE : T1110 | ISO 27001 : A.9.4.3 | NIST : PR.AC-7
        """
    },
    {
        "id": "db_xp_cmdshell_001",
        "domain": "db",
        "anomaly_type": "Exécution OS via DB",
        "content": """
        Description : Utilisation de procédures pour exécuter des commandes shell.
        Indicateurs : Usage de 'xp_cmdshell' (MSSQL) ou 'COPY FROM PROGRAM' (Postgres).
        Causes : Attaquant cherchant à rebondir de la DB vers l'OS.
        Actions : Désactiver la fonction, isoler serveur DB. Remédiation : Hardening instance.
        Prévention : Désactiver les fonctions OS-integration par défaut. Criticité : Critical.
        MITRE : T1059 | ISO 27001 : A.12.1.2 | NIST : PR.PT-4
        """
    },
    {
        "id": "db_proc_tamper_001",
        "domain": "db",
        "anomaly_type": "Altération Procédure",
        "content": """
        Description : Modification d'une procédure stockée critique (virement).
        Indicateurs : CREATE OR REPLACE FUNCTION sur une fonction de transaction.
        Causes : Détournement de fonds via manipulation de la logique DB.
        Actions : Restaurer code depuis Git, auditer auteur. Remédiation : Signature procedures.
        Prévention : CI/CD pour déploiement DB uniquement. Criticité : Critical.
        MITRE : T1565.001 | ISO 27001 : A.14.2.1 | NIST : PR.DS-1
        """
    },
    {
        "id": "db_audit_disable_001",
        "domain": "db",
        "anomaly_type": "Désactivation Audit DB",
        "content": """
        Description : Arrêt des logs de surveillance de la base de données.
        Indicateurs : Alerte 'Audit policy changed' ou 'Logging set to OFF'.
        Causes : Attaquant masquant ses extractions de données.
        Actions : Réactiver audit, vérifier logs SIEM. Remédiation : Envoi logs distant.
        Prévention : Protection anti-tamper sur les fichiers de log. Criticité : High.
        MITRE : T1562.001 | ISO 27001 : A.12.4.2 | NIST : PR.PT-1
        """
    },
    {
        "id": "db_asym_rw_001",
        "domain": "db",
        "anomaly_type": "Ratio RW anormal",
        "content": """
        Description : Pic massif de lecture (Read) sans écriture (Write) correspondante.
        Indicateurs : I/O Read > 10x la moyenne habituelle.
        Causes : Tentative de dumping de données de masse.
        Actions : Identifier session responsable, analyser requêtes. Remédiation : Quotas I/O.
        Prévention : Monitoring de performance granulaire. Criticité : Medium.
        MITRE : T1020 | ISO 27001 : A.18.1.1 | NIST : DE.CM-3
        """
    },
    {
        "id": "db_side_channel_001",
        "domain": "db",
        "anomaly_type": "Fuite Canal Auxiliaire",
        "content": """
        Description : Déduction de données via temps de réponse (Inference).
        Indicateurs : Requêtes répétitives avec variations de latence de quelques ms.
        Causes : Attaque par canal auxiliaire visant des données chiffrées.
        Actions : Rate-limit, audit requêtes complexes. Remédiation : Constant-time functions.
        Prévention : Limitation de la précision des timers. Criticité : Medium.
        MITRE : T1592 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "db_ransomware_db_001",
        "domain": "db",
        "anomaly_type": "Ransomware DB",
        "content": """
        Description : Chiffrement des fichiers .mdf / .ibd / .db.
        Indicateurs : Instance DB indisponible, fichiers chiffrés sur disque (OS).
        Causes : Infection directe du serveur de base de données.
        Actions : Incident P1 corp, isolation physique, PCA. Remédiation : Restauration backups.
        Prévention : Backups immuables offline, verrouillage OS. Criticité : Critical.
        MITRE : T1486 | ISO 27001 : A.17.1.1 | NIST : RS.RP-1
        """
    },
    {
        "id": "db_sec_table_tamper_001",
        "domain": "db",
        "anomaly_type": "Altération Table Sec",
        "content": """
        Description : Modification de la table des utilisateurs ou des rôles applicatifs.
        Indicateurs : UPDATE sur 'auth_user' ou 'permissions' directement en DB.
        Causes : Escalade de privilèges applicative via bypass backend.
        Actions : Vérifier intégrité des rôles, reset passwords. Remédiation : Audit triggers.
        Prévention : Triggers d'audit sur tables sensibles. Criticité : High.
        MITRE : T1078 | ISO 27001 : A.9.4.2 | NIST : PR.AC-3
        """
    },
    {
        "id": "db_default_cred_001",
        "domain": "db",
        "anomaly_type": "Identifiants par défaut",
        "content": """
        Description : Utilisation d'un mot de passe par défaut (ex: manager/manager).
        Indicateurs : Connexion réussie avec des couples user/pass triviaux.
        Causes : Oubli de sécurisation lors de l'installation.
        Actions : Changer mot de passe immediatement. Remédiation : Hardening script.
        Prévention : Scan de configuration (Post-install check). Criticité : Medium.
        MITRE : T1078 | ISO 27001 : A.12.6.1 | NIST : PR.AC-1
        """
    },
    {
        "id": "db_version_leak_001",
        "domain": "db",
        "anomaly_type": "Fuite Version DB",
        "content": """
        Description : Exposition de la version exacte de la DB dans les bannières ou erreurs.
        Indicateurs : Bannière 'PostgreSQL 9.6.1' visible sur port public.
        Causes : Mauvaise configuration du service.
        Actions : Masquer bannières, restreindre accès. Remédiation : Config 'extra_float_digits' etc.
        Prévention : Sécurisation des bannières de services. Criticité : Low.
        MITRE : T1592 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "db_clear_pass_001",
        "domain": "db",
        "anomaly_type": "Password en clair",
        "content": """
        Description : Détection de mots de passe stockés sans hashage.
        Indicateurs : Requête SELECT montrant des chaines lisibles dans colonne 'pwd'.
        Causes : Erreur de design cryptographique.
        Actions : Arrêter service, migrer données vers Argon2/BCrypt. Remédiation : Re-design.
        Prévention : Audit de schéma régulier. Criticité : High.
        MITRE : T1552 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "db_lock_exhaust_001",
        "domain": "db",
        "anomaly_type": "Saturation Verrous",
        "content": """
        Description : Transaction malveillante bloquant des milliers de lignes (Locks).
        Indicateurs : Hausse exponentielle des 'Waiting queries' (>100).
        Causes : Tentative de DoS sur les transactions bancaires.
        Actions : Kill transaction bloquante, identifier source. Remédiation : Timeout verrous.
        Prévention : Limitation de la durée des transactions. Criticité : High.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "db_log_del_001",
        "domain": "db",
        "anomaly_type": "Suppression Binary Log",
        "content": """
        Description : Effacement manuel des fichiers de transaction (binlogs/WAL).
        Indicateurs : Trou dans la séquence des fichiers log sur disque.
        Causes : Attaquant empêchant la reconstruction des transactions (Audit bypass).
        Actions : Vérifier répliques, investiguer accès OS. Remédiation : Log protection.
        Prévention : Forwarding logs temps réel. Criticité : High.
        MITRE : T1070.001 | ISO 27001 : A.12.4.2 | NIST : PR.PT-1
        """
    },
    {
        "id": "db_plan_tamper_001",
        "domain": "db",
        "anomaly_type": "Altération Plan Req",
        "content": """
        Description : Manipulation des statistiques pour forcer des plans de requête inefficients.
        Indicateurs : 'Explain Plan' incohérent, saturation CPU soudaine sur requêtes simples.
        Causes : Sabotage visant à ralentir le Core Banking.
        Actions : Recalculer stats (ANALYZE), auditer sessions. Remédiation : Freeze plans.
        Prévention : Audit des commandes statistiques. Criticité : Medium.
        MITRE : T1499 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },
    {
        "id": "db_conn_saturated_001",
        "domain": "db",
        "anomaly_type": "Saturation Connexions",
        "content": """
        Description : Occupation de tous les slots de connexion (max_connections).
        Indicateurs : Erreur 'Too many connections', status DB injoignable.
        Causes : Attaque DoS ou fuite de connexion applicative.
        Actions : Kill connexions idle, augmenter limite temporairement. Remédiation : Pooling.
        Prévention : Connection pooling (PgBouncer/Hikari). Criticité : High.
        MITRE : TA0042 | ISO 27001 : A.17.1.1 | NIST : PR.PT-4
        """
    },

    # ========== NEW GENERAL ENTRIES (20) ==========
    {
        "id": "gen_apt_activity_001",
        "domain": "general",
        "anomaly_type": "Activité APT",
        "content": """
        Description : Détection de patterns liés à des groupes d'attaque étatiques (APT28/29).
        Indicateurs : Usage d'outils spécifiques (Cobalt Strike), C2 connus, exfiltration furtive.
        Causes : Espionnage ou sabotage de l'infrastructure financière nationale.
        Actions : Alerter CERT national, isolement total, investigation profonde.
        Prévention : Threat Intelligence proactive, EDR. Criticité : Critical.
        MITRE : TA0001 | ISO 27001 : A.12.6.1 | NIST : DE.CM-1
        """
    },
    {
        "id": "gen_supply_chain_001",
        "domain": "general",
        "anomaly_type": "Attaque Supply Chain",
        "content": """
        Description : Compromission via un fournisseur ou une librairie tierce (SolarWinds style).
        Indicateurs : Update logiciel officiel contenant du code malveillant.
        Causes : Intrusion chez un partenaire technologique.
        Actions : Vérifier intégrité binaire, stopper updates, auditer trafic.
        Prévention : Code signing verification, SBOM (Software Bill of Materials). Criticité : Critical.
        MITRE : T1195 | ISO 27001 : A.15.1.1 | NIST : ID.SC-1
        """
    },
    {
        "id": "gen_shadow_it_001",
        "domain": "general",
        "anomaly_type": "Shadow IT Extension",
        "content": """
        Description : Déploiement massif de ressources Cloud sans approbation sécu.
        Indicateurs : Nouvelles zones AWS/Azure facturées sans projet identifié.
        Causes : Equipes dev contournant les processus d'achat.
        Actions : Geler ressources, auditer usage. Remédiation : Intégration gouvernance.
        Prévention : Cloud Security Posture Management (CSPM). Criticité : Medium.
        MITRE : T1583 | ISO 27001 : A.12.1.2 | NIST : PR.IP-1
        """
    },
    {
        "id": "gen_leak_darkweb_001",
        "domain": "general",
        "anomaly_type": "Fuite Dark Web",
        "content": """
        Description : Détection de bases de données de la banque en vente sur le Dark Web.
        Indicateurs : Alertes de monitoring externe (Threat Intel).
        Causes : Exfiltration passée non détectée ou vol chez un partenaire.
        Actions : Reset tous les comptes, identifier origine, notifier autorité protection données.
        Prévention : Monitoring externe continu. Criticité : Critical.
        MITRE : T1589 | ISO 27001 : A.12.6.1 | NIST : RS.RP-1
        """
    },
    {
        "id": "gen_cloud_compromise_001",
        "domain": "general",
        "anomaly_type": "Compromission Cloud Admin",
        "content": """
        Description : Accès au portail Azure/AWS par un compte admin depuis une IP suspecte.
        Indicateurs : Modification de politiques IAM critiques hors-heures.
        Causes : Accès MFA bypassé ou vol de session (Session Hijacking).
        Actions : Révoquer accès, forcer changement credentials globaux.
        Prévention : Conditional Access rules, MFA physique (FIDO2). Criticité : Critical.
        MITRE : T1078.004 | ISO 27001 : A.9.2.2 | NIST : PR.AC-2
        """
    },
    {
        "id": "gen_phishing_internal_001",
        "domain": "general",
        "anomaly_type": "Phishing Interne",
        "content": """
        Description : Campagne de phishing envoyée depuis un compte collaborateur compromis.
        Indicateurs : Hausse des signalements mails suspects en interne.
        Causes : Un premier compte a été victime de vol d'identifiant.
        Actions : Supprimer mails des boîtes, verrouiller compte source.
        Prévention : Formation continue, simulateur de phishing. Criticité : High.
        MITRE : T1566.002 | ISO 27001 : A.7.2.2 | NIST : PR.AT-1
        """
    },
    {
        "id": "gen_geopolit_001",
        "domain": "general",
        "anomaly_type": "Surcharge Géopolitique",
        "content": """
        Description : Pic d'attaques coordonné avec un événement international majeur.
        Indicateurs : Multiples alertes (FW, OS, App) synchronisées avec l'actualité.
        Causes : Hacktivisme ou représailles étatiques.
        Actions : Monter niveau d'alerte SOC, activer astreintes renforcées.
        Prévention : Monitoring de l'actualité géopolitique (Cyber Intel). Criticité : High.
        MITRE : TA0001 | ISO 27001 : A.12.6.1 | NIST : ID.BE-5
        """
    },
    {
        "id": "gen_complete_chain_001",
        "domain": "general",
        "anomaly_type": "Chaîne d'Attaque (Kill Chain)",
        "content": """
        Description : Corrélation d'au moins 3 pipelines différents pointant vers la même cible.
        Indicateurs : Scan (FW) -> RDP Brute force (OS) -> Slow query (DB).
        Causes : Intrusion active en phase de pivotage.
        Actions : Isoler machine cible immediately, analyse forensique temps réel.
        Prévention : Moteur de corrélation multi-dimensionnel. Criticité : Critical.
        MITRE : TA0002 | ISO 27001 : A.16.1.2 | NIST : DE.AE-5
        """
    },
    {
        "id": "gen_policy_tamper_001",
        "domain": "general",
        "anomaly_type": "Altération Politique Globale",
        "content": """
        Description : Désactivation de paramètres de sécurité au niveau SIEM/EDR global.
        Indicateurs : Taux de détection chutant de 50% sans raison technique.
        Causes : Attaquant de haut niveau "aveuglant" la défense.
        Actions : Vérifier config outils sécu, roll back, investiguer admins sécu.
        Prévention : Double-validation pour changements de politique globale. Criticité : Critical.
        MITRE : T1562 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "gen_sensor_silence_001",
        "domain": "general",
        "anomaly_type": "Silence Senseurs",
        "content": """
        Description : Arrêt brutal des flux de logs en provenance d'une zone entière.
        Indicateurs : Pas de logs reçus sur le SIEM depuis 1h pour Zone_DMZ.
        Causes : Coupure réseau ou action malveillante d'aveuglement.
        Actions : Vérifier connectivité, inspecter machines sur site.
        Prévention : Dead man switch alert (alerte si absence de logs). Criticité : High.
        MITRE : T1562.001 | ISO 27001 : A.12.4.2 | NIST : DE.CM-1
        """
    },
    {
        "id": "gen_hvt_anomaly_001",
        "domain": "general",
        "anomaly_type": "Anomalie HVT (VIP)",
        "content": """
        Description : Comportement atypique sur un compte de cadre dirigeant (CEO/CFO).
        Indicateurs : Accès à des systèmes techniques par un profil business à 23h.
        Causes : Whaling ou vol d'identifiants sensible.
        Actions : Appel de confirmation immédiat, gel temporaire accès.
        Prévention : Surveillance renforcée des comptes VIP. Criticité : Critical.
        MITRE : T1078 | ISO 27001 : A.9.2.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "gen_pki_theft_001",
        "domain": "general",
        "anomaly_type": "Vol Clé PKI",
        "content": """
        Description : Extraction de la clé privée de l'autorité de certification interne.
        Indicateurs : Alerte accès fichier HSM ou export de certificat root.
        Causes : Préparation d'une interception totale du trafic bancaire.
        Actions : Révoquer certificat racine, ré-émettre TOUS les certificats (Plan de secours).
        Prévention : Stockage en HSM physique uniquement. Criticité : Critical.
        MITRE : T1552.004 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "gen_lateral_pivot_001",
        "domain": "general",
        "anomaly_type": "Pivot Latéral",
        "content": """
        Description : Une machine compromise utilisée comme proxy pour attaquer les voisins.
        Indicateurs : Host_A (DMZ) scannant Host_B (LAN) sur ports sensibles (445, 22).
        Causes : Phase post-exploitation d'une intrusion.
        Actions : Isoler Host_A, nettoyer Host_B, vérifier comptes.
        Prévention : Micro-segmentation, EDR avec détection de scan. Criticité : High.
        MITRE : T1021 | ISO 27001 : A.13.1.1 | NIST : PR.AC-5
        """
    },
    {
        "id": "gen_physical_breach_001",
        "domain": "general",
        "anomaly_type": "Brèche Physique",
        "content": """
        Description : Entrée forcée ou badgeage suspect au DataCenter.
        Indicateurs : Alerte intrusion GTC corrélée avec extinction serveurs.
        Causes : Sabotage physique ou vol de serveurs bancaires.
        Actions : Alerter police, déclencher PCA physique, verrouiller accès logiques.
        Prévention : Vidéosurveillance, accès biométrique. Criticité : Critical.
        MITRE : T1052 | ISO 27001 : A.11.1.1 | NIST : PR.IP-5
        """
    },
    {
        "id": "gen_whaling_fraud_001",
        "domain": "general",
        "anomaly_type": "Fraude au Président",
        "content": """
        Description : Mail d'un dirigeant demandant un virement urgent hors procédure.
        Indicateurs : Langage inhabituel, pression temporelle, destinataire hors liste habituelle.
        Causes : Ingénierie sociale ciblée.
        Actions : Bloquer virement, informer direction, bloquer domaine mail expéditeur.
        Prévention : Procédures virement strictes, formation. Criticité : Critical.
        MITRE : T1566.002 | ISO 27001 : A.7.2.2 | NIST : PR.AT-1
        """
    },
    {
        "id": "gen_git_leak_001",
        "domain": "general",
        "anomaly_type": "Fuite Git Secret",
        "content": """
        Description : Secrets (mots de passe, clés API) committés en clair sur GitHub.
        Indicateurs : Alerte de scanner de secrets (Trufflehog).
        Causes : Erreur de développeur, absence de .gitignore.
        Actions : Révoquer secret, supprimer historique, ré-émettre clé.
        Prévention : Pre-commit hooks for secret detection. Criticité : High.
        MITRE : T1552.001 | ISO 27001 : A.14.2.1 | NIST : PR.IP-1
        """
    },
    {
        "id": "gen_gdpr_breach_001",
        "domain": "general",
        "anomaly_type": "Brèche RGPD",
        "content": """
        Description : Exposition publique de données personnelles (PII) clients.
        Indicateurs : URL ouverte au public listant des noms/soldes sans auth.
        Causes : Erreur de configuration de stockage (S3 public) ou bug app.
        Actions : Fermer accès, notifier CNIL (72h), notifier clients si risque élevé.
        Prévention : Scans de surface d'attaque externe. Criticité : High.
        MITRE : T1020 | ISO 27001 : A.18.1.1 | NIST : RS.RP-1
        """
    },
    {
        "id": "gen_dr_trigger_001",
        "domain": "general",
        "anomaly_type": "Déclenchement DR Suspect",
        "content": """
        Description : Bascule sur le site de secours sans sinistre majeur déclaré.
        Indicateurs : Activation des flux répliques DB et routage réseau vers site B.
        Causes : Tentative d'attaquant de saboter la production ou de tester la défense.
        Actions : Identifier auteur commande, vérifier intégrité site B.
        Prévention : Contrôles d'accès redondants sur gestionnaire DR. Criticité : Medium.
        MITRE : T1562 | ISO 27001 : A.17.1.1 | NIST : PR.IP-9
        """
    },
    {
        "id": "gen_golden_ticket_001",
        "domain": "general",
        "anomaly_type": "Golden Ticket AD",
        "content": """
        Description : Accès persistant via ticket Kerberos forgé (Compromission AD).
        Indicateurs : EventID 4624 avec des paramètres Kerberos incohérents.
        Causes : Vol de la clé KRBTGT.
        Actions : Changer mot de passe KRBTGT deux fois, forcer re-login global.
        Prévention : Privileged Access Workstations (PAW), Tiering AD. Criticité : Critical.
        MITRE : T1558.001 | ISO 27001 : A.9.2.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "gen_backup_corr_001",
        "domain": "general",
        "anomaly_type": "Corruption Sauvegarde",
        "content": """
        Description : Sauvegardes devenues illisibles ou corrompues.
        Indicateurs : Echec systématique des tests de restauration.
        Causes : Malware s'attaquant aux archives avant le chiffrement final.
        Actions : Tenter restauration archives offline (Cold storage), incident majeur.
        Prévention : Vérification checksum régulière des backups. Criticité : Critical.
        MITRE : T1485 | ISO 27001 : A.12.3.1 | NIST : PR.IP-4
        """
    },

    # ========== NEW ISO27000 ENTRIES (20) ==========
    {
        "id": "iso_no_inventory_001",
        "domain": "iso27000",
        "anomaly_type": "Défaut d'Inventaire",
        "content": """
        Description : Actif critique non présent dans l'inventaire matériel/logiciel.
        Indicateurs : Détection de système non managé par le scan de vulnérabilités.
        Causes : Absence de processus d'accueil des nouveaux actifs.
        Remédiation : Recensement immédiat, intégration CMDB.
        Prévention : NAC (Network Access Control). Criticité : Medium.
        MITRE : T1583 | ISO 27001 : A.8.1.1 | NIST : ID.AM-1
        """
    },
    {
        "id": "iso_no_review_001",
        "domain": "iso27000",
        "anomaly_type": "Défaut Revue Accès",
        "content": """
        Description : Droits d'accès d'un collaborateur muté n'ayant pas été révisés.
        Indicateurs : Ancien admin système gardant ses droits après passage au marketing.
        Causes : Absence de notification entre RH et IT.
        Remédiation : Suppression immédiate des droits obsolètes.
        Prévention : Revue de comptes trimestrielle. Criticité : Medium.
        MITRE : T1078 | ISO 27001 : A.9.2.5 | NIST : PR.AC-2
        """
    },
    {
        "id": "iso_weak_crypto_001",
        "domain": "iso27000",
        "anomaly_type": "Cryptographie Faible",
        "content": """
        Description : Utilisation d'algorithmes dépréciés (MD5, DES, TLS 1.0).
        Indicateurs : Alertes SSL Scan montrant des vulnérabilités béantes.
        Causes : Systèmes legacy non mis à jour.
        Remédiation : Migration vers AES-256 / SHA-256 / TLS 1.2+.
        Prévention : Gestion centrale des certificats et protocoles. Criticité : High.
        MITRE : T1573 | ISO 27001 : A.10.1.1 | NIST : PR.DS-2
        """
    },
    {
        "id": "iso_phys_disc_001",
        "domain": "iso27000",
        "anomaly_type": "Discrepance Log Phys",
        "content": """
        Description : Incohérence entre les sorties du bâtiment et les sessions logiques.
        Indicateurs : Un PC d'admin est utilisé alors que l'admin est sorti du bâtiment (badge).
        Causes : Tailgating physique ou vol de session.
        Remédiation : Verrouillage immédiat de la session, investigation vidéo.
        Prévention : Corrélation logs logiques et physiques (UBA). Criticité : High.
        MITRE : T1550 | ISO 27001 : A.11.1.2 | NIST : PR.AC-1
        """
    },
    {
        "id": "iso_no_rfc_001",
        "domain": "iso27000",
        "anomaly_type": "Changement sans RFC",
        "content": """
        Description : Modification majeure en production sans ticket de changement (RFC).
        Indicateurs : Diff de config détecté par outils d'automatisation sans évènement ITSM.
        Causes : Action admin en direct, "Quick fix" dangereux.
        Remédiation : Rollback, audit par les pairs.
        Prévention : Déploiements pilotés par CI/CD uniquement. Criticité : Medium.
        MITRE : T1562 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "iso_tls_disable_001",
        "domain": "iso27000",
        "anomaly_type": "Désactivation TLS",
        "content": """
        Description : Canal de communication passé en clair sans raison valable.
        Indicateurs : Trafic port 80 (HTTP) détecté vers serveurs de paiement.
        Causes : Mauvaise configuration ponctuelle ou tentative d'interception.
        Remédiation : Rétablir HTTPS immédiat, forcer redirections.
        Prévention : Politique HSTS et certificats obligatoires. Criticité : High.
        MITRE : T1557 | ISO 27001 : A.13.1.2 | NIST : PR.DS-2
        """
    },
    {
        "id": "iso_sdlc_bypass_001",
        "domain": "iso27000",
        "anomaly_type": "Contournement SDLC",
        "content": """
        Description : Mise en production directe sans passer par les tests de sécurité.
        Indicateurs : Absence de rapport de scan DAST/SAST pour le binaire courant.
        Causes : Urgence business court-circuitant la cybersécurité.
        Remédiation : Scan de vulnérabilités a posteriori, patching d'urgence.
        Prévention : Pipeline DevSecOps as a Service. Criticité : Medium.
        MITRE : T1195 | ISO 27001 : A.14.2.1 | NIST : PR.IP-2
        """
    },
    {
        "id": "iso_supplier_risk_001",
        "domain": "iso27000",
        "anomaly_type": "Risque Fournisseur",
        "content": """
        Description : Accès au réseau de la banque par un prestataire dont le contrat a expiré.
        Indicateurs : VPN actif pour un compte de partenaire inactif.
        Causes : Oubli de clôture d'accès fournisseur.
        Remédiation : Fermeture immédiate du compte.
        Prévention : Intégration des contrats fournisseurs dans l'IAM. Criticité : High.
        MITRE : T1078.003 | ISO 27001 : A.15.1.3 | NIST : ID.SC-3
        """
    },
    {
        "id": "iso_unrep_incid_001",
        "domain": "iso27000",
        "anomaly_type": "Incident non reporté",
        "content": """
        Description : Découverte fortuite d'une brèche ayant eu lieu il y a plusieurs semaines.
        Indicateurs : Présence de malwares historiques sur un serveur non audité.
        Causes : Peur de sanction ou défaut de culture de signalement.
        Remédiation : Analyse de l'impact rétroactif, renforcement formation.
        Prévention : Ligne de signalement anonyme, culture 'No Blame'. Criticité : High.
        MITRE : T1562 | ISO 27001 : A.16.1.1 | NIST : RS.RP-1
        """
    },
    {
        "id": "iso_bcp_fail_001",
        "domain": "iso27000",
        "anomaly_type": "Echec Test PCA",
        "content": """
        Description : Impossible de démarrer les services sur le site de repli.
        Indicateurs : Echec du test annuel de continuité d'activité.
        Causes : Manque de ressources (CPU/RAM) sur le site B, configuration obsolète.
        Remédiation : Mise à jour immédiate du stock matériel du site B.
        Prévention : Tests de basculement semestriels. Criticité : Critical.
        MITRE : T1562 | ISO 27001 : A.17.1.3 | NIST : ID.BE-4
        """
    },
    {
        "id": "iso_license_gap_001",
        "domain": "iso27000",
        "anomaly_type": "Gap Réglementaire",
        "content": """
        Description : Expiration d'une licence ou d'une certification légale.
        Indicateurs : Date de validité du certificat de conformité PCI-DSS dépassée.
        Causes : Mauvaise gestion des renouvellements.
        Remédiation : Audit éclair, renouvellement d'urgence.
        Prévention : Calendrier de conformité partagé. Criticité : Medium.
        MITRE : T1583 | ISO 27001 : A.18.1.1 | NIST : ID.GV-3
        """
    },
    {
        "id": "iso_info_class_001",
        "domain": "iso27000",
        "anomaly_type": "Défaut Classification",
        "content": """
        Description : Données classées 'Secret Médical' stockées en zone 'Public'.
        Indicateurs : Alerte DLP sur des tags de métadonnées sensibles en zone non-sécurisée.
        Causes : Mauvaise manipulation ou méconnaissance de la sensibilité.
        Remédiation : Déplacement des données, chiffrement.
        Prévention : Classification automatique des données. Criticité : High.
        MITRE : T1020 | ISO 27001 : A.8.2.1 | NIST : PR.DS-1
        """
    },
    {
        "id": "iso_prohib_soft_001",
        "domain": "iso27000",
        "anomaly_type": "Logiciel Prohibé",
        "content": """
        Description : Installation d'un client Peer-to-Peer sur un poste sensible (Risk Management).
        Indicateurs : Alerte proxy sur trafic BitTorrent.
        Causes : Employé contournant les règles d'utilisation acceptable.
        Remédiation : Désinstallation immédiate, sanction administrative.
        Prévention : Liste blanche d'applications autorisées. Criticité : Medium.
        MITRE : T1204.002 | ISO 27001 : A.8.1.3 | NIST : PR.IP-1
        """
    },
    {
        "id": "iso_sod_violation_001",
        "domain": "iso27000",
        "anomaly_type": "Violation SoD",
        "content": """
        Description : Un seul utilisateur capable de créer ET de valider un virement.
        Indicateurs : Logs montrant les deux étapes réalisées par le même UID.
        Causes : Droit d'accès cumulatifs non détectés (Toxic Combination).
        Remédiation : Scission immédiate des pouvoirs, audit des virements passés.
        Prévention : Matrice de Séparation des Tâches automatisée. Criticité : Critical.
        MITRE : T1078 | ISO 27001 : A.6.1.2 | NIST : PR.AC-4
        """
    },
    {
        "id": "iso_retention_fail_001",
        "domain": "iso27000",
        "anomaly_type": "Défaut Rétention Log",
        "content": """
        Description : Logs de plus d'un an (légal) auto-supprimés par manque d'espace.
        Indicateurs : Impossible de trouver un log datant de 10 mois.
        Causes : Politique d'archivage non testée.
        Remédiation : Extension stockage, gel des suppressions.
        Prévention : Monitoring de l'espace de rétention légale. Criticité : Medium.
        MITRE : T1070 | ISO 27001 : A.12.4.1 | NIST : PR.PT-1
        """
    },
    {
        "id": "iso_patch_sl_001",
        "domain": "iso27000",
        "anomaly_type": "Dépassement SLA Patch",
        "content": """
        Description : Vulnérabilité 'Critical' non patchée après 48h.
        Indicateurs : Scans Qualys/Nessus montrant CVE tjs présente sur périmètre exposé.
        Causes : Manque de bande passante technique ou blocage par application legacy.
        Remédiation : Patching immédiat, mise sous WAF temporaire.
        Prévention : Dashboard de suivi des SLA de vulnérabilité. Criticité : High.
        MITRE : T1210 | ISO 27001 : A.12.6.1 | NIST : PR.IP-12
        """
    },
    {
        "id": "iso_restore_fail_001",
        "domain": "iso27000",
        "anomaly_type": "Echec Test Restauration",
        "content": """
        Description : Les données sauvegardées ne peuvent pas être remontées sur l'environnement de test.
        Indicateurs : Erreur CRC lors de l'extraction des archives SQL.
        Causes : Bandes défectueuses ou mauvaise config de l'agent de backup.
        Remédiation : Vérifier les redondances de sauvegarde (3-2-1 rule).
        Prévention : Tests de restauration mensuels automatiques. Criticité : Critical.
        MITRE : T1485 | ISO 27001 : A.12.3.1 | NIST : PR.IP-4
        """
    },
    {
        "id": "iso_edr_removal_001",
        "domain": "iso27000",
        "anomaly_type": "Retrait Agent EDR",
        "content": """
        Description : Machine sensible n'envoyant plus de battement de coeur de sécurité.
        Indicateurs : Statut 'Disconnected' sur le dashboard EDR/AV.
        Causes : Désactivation par attaquant ou problème de mise à jour.
        Remédiation : Isoler machine, réinstallation forcée.
        Prévention : Protection anti-désinstallation avec mot de passe. Criticité : Critical.
        MITRE : T1562.001 | ISO 27001 : A.12.2.1 | NIST : DE.CM-1
        """
    },
    {
        "id": "iso_emerg_change_abuse_001",
        "domain": "iso27000",
        "anomaly_type": "Abus Changement Urgence",
        "content": """
        Description : Passage systématique de changements mineurs en tant que 'Emergency Change'.
        Indicateurs : Taux de changements urgents > 50% de la volumétrie totale.
        Causes : Contournement de la validation sécu standard.
        Remédiation : Revue des changements par le COMOP sécu.
        Prévention : Limitation du nombre de RFC Urgentes par mois. Criticité : Low.
        MITRE : T1562 | ISO 27001 : A.12.1.2 | NIST : PR.IP-3
        """
    },
    {
        "id": "iso_capacity_limit_001",
        "domain": "iso27000",
        "anomaly_type": "Seuil Capacité Atteint",
        "content": """
        Description : Saturation prévisible des ressources impactant la disponibilité du SOC.
        Indicateurs : Stockage SIEM > 95%, CPU collecteurs à 100%.
        Causes : Mauvaise planification de la capacité de traitement.
        Remédiation : Extension ressources, filtrage des logs non-critiques.
        Prévention : Capacity planning annuel obligatoire. Criticité : Medium.
        MITRE : T1499 | ISO 27001 : A.12.1.3 | NIST : PR.PT-4
        """
    },
]




def load_pdf_knowledge(pdf_path: str, chunk_size: int = 800, chunk_overlap: int = 150):
    """
    Charge un PDF, nettoie le texte et le découpe en chunks avec métadonnées.
    """
    if not PdfReader or not os.path.exists(pdf_path):
        return []

    try:
        reader = PdfReader(pdf_path)
        pages_content = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text = re.sub(r'\s+', ' ', text).strip()
                pages_content.append({"text": text, "page": i + 1})

        chunks = []
        current_chunk_id = 0
        
        for page_data in pages_content:
            text = page_data["text"]
            page_num = page_data["page"]
            
            words = text.split()
            for j in range(0, len(words), chunk_size - chunk_overlap):
                chunk_words = words[j:j + chunk_size]
                if not chunk_words:
                    break
                
                chunk_text = " ".join(chunk_words)
                chunks.append({
                    "id": f"iso27000_p{page_num}_{current_chunk_id}",
                    "domain": "iso27000",
                    "anomaly_type": "ISO 27000 Guideline",
                    "content": chunk_text,
                    "metadata": {
                        "source": "ISO27000",
                        "page_number": page_num,
                        "chunk_id": current_chunk_id
                    }
                })
                current_chunk_id += 1
        
        return chunks
    except Exception as e:
        print(f"Error loading PDF {pdf_path}: {e}")
        return []

def get_all_documents(include_pdf: bool = True):
    """Retourne tous les documents de la base de connaissances (statiques + PDF)"""
    docs = list(SECURITY_KNOWLEDGE)
    if include_pdf:
        pdf_path = Path(__file__).resolve().parent / "ISO27000_Guide_Detaille.pdf"
        if pdf_path.exists():
            pdf_docs = load_pdf_knowledge(str(pdf_path))
            docs.extend(pdf_docs)
    return docs

def get_documents_by_domain(domain: str):
    """Filtre par domaine"""
    all_docs = get_all_documents()
    return [d for d in all_docs if d["domain"] in (domain, "general", "iso27000")]

def get_document_by_anomaly_type(anomaly_type: str):
    """Cherche un document par type d'anomalie"""
    at_lower = anomaly_type.lower().strip()
    all_docs = get_all_documents()
    for doc in all_docs:
        if doc["anomaly_type"].lower() == at_lower:
            return doc
    for doc in all_docs:
        if doc["anomaly_type"].lower() in at_lower or at_lower in doc["anomaly_type"].lower():
            return doc
    return None
