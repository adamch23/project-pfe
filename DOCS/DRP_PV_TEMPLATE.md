# TEMPLATE PV — EXERCICE DRP BANKING GRADE
## Finding BCP-02 (Audit Bancaire) | DORA Art. 26 | ISO 27001 A.17.1.3
## Classification : CONFIDENTIEL — Diffusion restreinte

---

# PROCÈS-VERBAL D'EXERCICE DE CONTINUITÉ D'ACTIVITÉ

**Référence :** DRP-DRILL-[YYYY]-[NN]
**Type d'exercice :** `☐ Tabletop` `☐ Simulation partielle` `☐ Failover complet`
**Date :** _______________
**Durée :** _______________
**Scénario :** _______________

---

## 1. PARTICIPANTS

| Nom | Rôle | Présence | Signature |
|---|---|:---:|---|
| | RSSI (Coordinateur) | ☐ Présent ☐ Excusé | |
| | Directeur IT | ☐ Présent ☐ Excusé | |
| | DevOps Lead | ☐ Présent ☐ Excusé | |
| | DBA | ☐ Présent ☐ Excusé | |
| | Observateur externe | ☐ Présent ☐ Excusé | |

---

## 2. DESCRIPTION DU SCÉNARIO SIMULÉ

**Type de panne simulé :**
`☐ Perte complète du serveur primaire`
`☐ Perte de la base de données MongoDB`
`☐ Attaque DDoS volumétrique`
`☐ Compromission de clés cryptographiques`
`☐ Ransomware (isolation réseau)`
`☐ Perte du datacenter primaire`

**Impact simulé :**
- Services affectés : _______________
- Données à risque : _______________
- Durée estimée de la panne réelle : _______________

---

## 3. CHRONOLOGIE DE L'EXERCICE

| Heure | Événement | Responsable | Durée | Statut |
|---|---|---|---|:---:|
| H+00:00 | Détection de l'incident (AlertManager) | DevOps | | ☐ OK ☐ KO |
| H+00:05 | Validation alerte P1 + notification RSSI | RSSI | | ☐ OK ☐ KO |
| H+00:15 | Décision de basculement (Go/No-Go) | RSSI + DIT | | ☐ OK ☐ KO |
| H+00:20 | Début du basculement DNS/Infra | DevOps | | ☐ OK ☐ KO |
| H+00:30 | Reprise de service sur site secondaire | DevOps + DBA | | ☐ OK ☐ KO |
| H+00:35 | Smoke tests post-basculement | DevOps | | ☐ OK ☐ KO |
| H+00:45 | Communication aux utilisateurs | RSSI | | ☐ OK ☐ KO |
| H+04:00 | RTO cible atteint (ou non) | Tous | | ☐ OK ☐ KO |

---

## 4. RÉSULTATS MESURÉS

### 4.1 SLAs vs Résultats Réels

| KPI | Cible SLA | Résultat Mesuré | Conformité |
|---|:---:|:---:|:---:|
| MTTD (détection) | ≤ 5 min | ___ min | ☐ ✅ ☐ ❌ |
| MTTR (résolution) | ≤ 30 min | ___ min | ☐ ✅ ☐ ❌ |
| RTO (reprise service) | ≤ 4h | ___ h | ☐ ✅ ☐ ❌ |
| RPO (perte de données) | ≤ 2h | ___ h | ☐ ✅ ☐ ❌ |
| Disponibilité pendant failover | > 0% secondary | ___% | ☐ ✅ ☐ ❌ |

### 4.2 Tests Techniques Exécutés

| Test | Description | Résultat |
|---|---|:---:|
| Healthcheck `/api/health` | Répond après basculement | ☐ ✅ ☐ ❌ |
| Authentification JWT | Tokens valides sur secondaire | ☐ ✅ ☐ ❌ |
| Accès MongoDB secondaire | Données accessibles (replica) | ☐ ✅ ☐ ❌ |
| Alerte AlertManager | Notification reçue (Slack/Email) | ☐ ✅ ☐ ❌ |
| Audit trail conservé | Logs intègres post-basculement | ☐ ✅ ☐ ❌ |
| Chiffrement fonctionnel | Déchiffrement biométrie OK | ☐ ✅ ☐ ❌ |

---

## 5. DIFFICULTÉS RENCONTRÉES & ACTIONS CORRECTIVES

| # | Problème rencontré | Impact | Action corrective | Responsable | Délai |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. POINTS FORTS OBSERVÉS

- _______________
- _______________
- _______________

---

## 7. VERDICT FINAL

**RTO respecté :** `☐ OUI` `☐ NON` — Résultat : ___ h (cible : ≤ 4h)
**RPO respecté :** `☐ OUI` `☐ NON` — Résultat : ___ h (cible : ≤ 2h)
**Exercice validé :** `☐ OUI` `☐ NON (re-drill requis dans 30 jours)`

**Avis du RSSI :**

> _______________

**Prochaine révision du PCA/DRP :** _______________

---

## 8. SIGNATURES

| Rôle | Nom | Date | Signature |
|---|---|---|---|
| RSSI (Approbateur) | | | |
| Directeur IT | | | |
| DevOps Lead | | | |
| Observateur externe | | | |

---

## ANNEXES

### A — Commandes exécutées pendant l'exercice

```bash
# Exemple : basculement DNS
# dig attijari-bank.tn                                    # Avant
# aws route53 change-resource-record-sets ...             # Basculement
# dig attijari-bank.tn                                    # Après

# Exemple : vérification MongoDB Replica Set
# mongosh "mongodb://mongo1:27017" --eval "rs.status()"

# Exemple : smoke tests post-basculement
# curl -f https://api.attijari-bank.tn/api/health
# python tests/load_test_banking.py --url https://api.attijari-bank.tn --scenario ci
```

### B — Références

- DORA Art. 26 — Digital Operational Resilience Testing
- ISO 27001 A.17.1.3 — Vérification, révision et évaluation de la continuité
- PCI-DSS Req. 12.10.7 — Exercices annuels du plan de réponse aux incidents

---
*PV généré par : Système de Gouvernance SI XAI Banking v3.0*
*Template référence : AUDIT-XAI-2026-001*
