# 📑 Plan de Continuité et de Reprise d'Activité (BCP/DRP)
> Version : 3.0 — Juin 2026 | Révisé post-Audit Bancaire Big 4 (AUDIT-XAI-2026-001)

---

## 0. Structure de Gouvernance SI (Finding GOV-01 — Résolu)

### 0.1 RSSI (Responsable Sécurité du Système d'Information)

| Rôle | Titulaire | Contact | Date de prise de fonction |
|---|---|---|---|
| RSSI | **[À NOMMER — Deadline : 30/07/2026]** | rssi@attijari-bank.internal | — |
| RSSI par intérim | Directeur IT / Tech Lead | it-director@attijari-bank.internal | Juin 2026 |
| Contact Audit | RSSI ou mandataire | audit@attijari-bank.internal | — |

> [!IMPORTANT]
> La nomination formelle du RSSI doit intervenir avant le **30/07/2026** pour être conforme à l'exigence ISO 27001 A.6.1.1 et DORA Art. 5. Cette nomination doit être approuvée par la Direction Générale et communiquée à l'autorité de tutelle (BCT).

### 0.2 Comité de Sécurité SI (COSSI)

Composition recommandée (réunion mensuelle + session extraordinaire sur incident P1) :
- Directeur Général (sponsor)
- RSSI (secrétaire)
- Directeur IT / Tech Lead
- Directeur des Risques
- Représentant Conformité (Compliance)
- Responsable Audit Interne

### 0.3 Politique de Sécurité (PSSI)

| Document | Version | Approbation | Prochaine révision |
|---|---|---|---|
| PSSI Globale | V1.0 (Draft) | **En attente direction** | Décembre 2026 |
| Politique de Mots de Passe | V2.0 | Tech Lead | Décembre 2026 |
| Politique de Classification | V1.0 | RSSI p.i. | Décembre 2026 |

---

## 1. Objectifs (SLA Bancaires)

- **RTO (Recovery Time Objective) :** ≤ 4 heures.
- **RPO (Recovery Point Objective) :** ≤ 2 heures (perte de données maximale autorisée).
- **Disponibilité cible :** 99.982% (Tier III).
- **MTTD (Mean Time to Detect) :** ≤ 5 minutes (AlertManager configuré).
- **MTTR (Mean Time to Resolve) :** ≤ 30 minutes sur incidents P1.

---

## 2. Stratégie de Résilience

### 2.1 Architecture Multi-Sites

L'infrastructure est déployée en mode **Active/Passive** sur deux régions Cloud isolées.
- **Site Primaire :** Cluster Docker Compose avec 2 réplicas minimum (scale backend=2).
- **Site de Secours :** Instance préchauffée (Warm Standby) — VM provisionnée en permanence,
  application déployée mais en veille. Basculement en < 30 min via switch DNS.
- **Prochaine étape :** Migration vers Active/Active (Roadmap Q4 2026).

### 2.2 Réplication des Données

- **MongoDB :** Replica Set avec journaling activé (roadmap Q3 2026 — Finding ARCH-01).
- **Backups :** Snapshots toutes les **2 heures** (aligné sur le RPO) avec export chiffré
  (AES-256) vers un bucket S3 immuable (Object Lock activé).
- **Variable d'activation :** `REQUIRE_S3_ARCHIVE_BEFORE_PURGE=true` en production.

### 2.3 Rétention des Données (PCI-DSS / BCT)

| Collection | Durée online | Archivage | Méthode de purge |
|---|---|---|---|
| `audit_logs` | 1 an | S3 Glacier (5 ans total) | Conditionnée à confirmation S3 |
| `biometric_logs` | 1 an | Purge sécurisée | Automatique (RGPD Art. 9) |
| `server.log` | 90 jours | Rotation + Loki | Automatique |

---

## 3. Procédure de Basculement (Failover)

1. **Détection :** Prometheus AlertManager — `InstanceDown` ≥ 1 min → alerte P1 (MTTD ≤ 5 min).
2. **Notification :** Escalade automatique via Slack #incidents-critiques + PagerDuty + Email DG.
3. **Décision (< 15 min) :** RSSI + Directeur IT valident le basculement.
4. **Redirection :** Switch DNS via Cloudflare/Route53 (TTL = 60s).
5. **Activation Warm Standby :** Démarrage de l'application sur le site secondaire.
6. **Validation :** Smoke tests automatisés post-basculement (`/api/health`).
7. **PV d'incident :** Rédaction du compte-rendu dans les 2 heures (format ITIL).

---

## 4. Procédure d'Escalade Incidents (Finding GOV-02 — Résolu)

### 4.1 Niveaux de Sévérité

| Niveau | Critères | MTTR cible | Escalade |
|---|---|---|---|
| **P1 — Critique** | Service indisponible, fuite de données, brute-force actif | ≤ 30 min | RSSI + DG + DSI immédiatement |
| **P2 — Élevé** | Dégradation sévère, latence P99 > 2s, erreurs 5xx > 5% | ≤ 2h | RSSI + Tech Lead |
| **P3 — Moyen** | Alerte non critique, dégradation mineure | ≤ 8h | Tech Lead |
| **P4 — Faible** | Anomalie cosmétique, dette technique | Planifié | Équipe dev |

### 4.2 Change Advisory Board (CAB) — Finding GOV-02

**Fréquence :** Chaque semaine (mercredi 14h) + session d'urgence si changement P1.

**Processus RFC (Request for Change) :**
1. Développeur crée une PR sur `develop` avec description d'impact.
2. Tech Lead approuve la PR (revue de code — 1er approbateur).
3. RSSI ou Directeur IT approuve pour les changements affectant la sécurité (2ème approbateur).
4. CAB valide le passage en `main` lors de la session hebdomadaire.
5. Déploiement en UAT → validation → déploiement PROD en fenêtre de maintenance.
6. Rollback plan documenté dans chaque PR (obligatoire).

**Fenêtres de maintenance PROD :** Mardi et jeudi, 22h–02h (heure locale TN).

> [!IMPORTANT]
> La branche `main` doit être protégée sur GitHub avec `require_reviewers: 2`.
> Aucun push direct sur `main` n'est autorisé (politique technique + politique organisationnelle).

---

## 5. Calendrier des Tests DRP (Drills)

| Trimestre | Type de Test | Participants | Résultat Attendu | Statut |
|---|---|---|---|---|
| Q2 2026 | Basculement DNS manuel | DevOps + RSSI | RTO validé ≤ 4h | 🔴 À planifier |
| Q3 2026 | Simulation perte MongoDB | DBA + Dev Lead | RPO validé ≤ 2h | 🔴 À planifier |
| Q4 2026 | DRP Drill complet | Toutes équipes | PV officiel | 🔴 À planifier |

> [!NOTE]
> Chaque drill doit produire un **Procès-Verbal (PV)** signé par le RSSI.
> Ce PV est requis pour la conformité DORA Art. 26 et l'audit annuel PCI-DSS.

---

## 6. Politique de Sécurité du SI (PSSI) — Mapping des Flux

### 6.1 Classification des Données

| Classe | Exemples | Accès | Contrôles |
|---|---|---|---|
| **C1 (Publique)** | Métadonnées IA non sensibles | Tous | Aucun contrôle spécifique |
| **C2 (Interne)** | Logs applicatifs standards | Équipe IT | Authentification requise |
| **C3 (Confidentielle)** | KYC, données transactionnelles | Rôle admin | RBAC + Audit trail |
| **C4 (Critique)** | Biométrie, clés privées RSA | RSSI + HSM | Vault + HSM + Audit signé HMAC |

### 6.2 Contrôles de Sécurité Implémentés

| Contrôle | Statut | Implémentation |
|---|---|---|
| Zéro Trust (mTLS inter-services) | 🔴 Roadmap | Q2 2027 |
| Audit Trail HMAC | ✅ Actif | `audit_service.py` |
| Gestion des secrets (Vault-ready) | ✅ Actif | `secret_manager.py` |
| Chiffrement biométrique AES-256 | ✅ Actif | `security_service.py` |
| Data Masking DEV/UAT | ✅ Script | `backend/scripts/data_masking.py` |
| Lockout anti-brute-force | ✅ Actif | `user_service.py` |
| Content-Security-Policy | ✅ Actif | `main.py` — middleware headers |
| Correlation ID par requête | ✅ Actif | `main.py` — middleware |
| Scan secrets CI/CD (gitleaks) | ✅ Actif | `.github/workflows/ci-cd.yml` |
| SCA dépendances (pip-audit) | ✅ Actif | `.github/workflows/ci-cd.yml` |

### 6.3 Gestion des Secrets

- **Développement :** Variables d'environnement via `.env` (exclu de Git par `.gitignore`).
- **Production :** Activer `VAULT_ENABLED=true` + configurer `VAULT_ADDR` et `VAULT_TOKEN`.
- **Clés RSA :** Injectées via Docker env `RSA_PRIVATE_KEY` / `RSA_PUBLIC_KEY` (jamais dans l'image).
- **Rotation :** Toutes les clés doivent être rotées tous les 12 mois (ou immédiatement si compromises).

---

*Document maintenu par : RSSI / Tech Lead*
*Classification : CONFIDENTIEL — Diffusion restreinte aux parties habilitées*
*Dernière révision : Juin 2026 — Post-Audit AUDIT-XAI-2026-001*
