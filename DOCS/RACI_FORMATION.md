# MATRICE RACI & PLAN DE FORMATION SÉCURITÉ
## Plateforme XAI Banking Grade — Gouvernance SI
## Finding GOV-04 (Audit Bancaire) | ISO 27001 A.7.2.2 | PCI-DSS Req. 12.6
## Version : 1.0 — Juin 2026 | Approuvé par : RSSI p.i.

---

## 1. MATRICE RACI — Systèmes et Accès Critiques

> **Légende :** R = Responsable (fait) | A = Approbateur (valide) | C = Consulté | I = Informé

### 1.1 Accès aux Secrets et Clés Cryptographiques

| Action | RSSI | Directeur IT | DevOps Lead | Développeur | DBA | Auditeur |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Génération paire RSA | R | A | R | I | — | I |
| Rotation des clés (annuelle) | A | A | R | C | — | I |
| Accès HashiCorp Vault | A | A | R | — | — | I |
| Révocation d'urgence (incident) | A | R | R | I | I | I |
| Audit des accès aux secrets | R | I | I | — | — | R |

### 1.2 Accès à la Base de Données MongoDB

| Action | RSSI | Directeur IT | DevOps Lead | Développeur | DBA | Auditeur |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Accès PROD (lecture) | A | I | — | — | R | R |
| Accès PROD (écriture) | A | A | — | — | R | I |
| Accès DEV/UAT | I | I | A | R | C | — |
| Backup et restore | I | A | R | — | R | I |
| Purge données (rétention) | A | I | — | — | R | R |

### 1.3 Déploiement et CI/CD

| Action | RSSI | Directeur IT | DevOps Lead | Développeur | DBA | Auditeur |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Push sur `develop` | I | I | A | R | — | — |
| Merge `develop` → `main` | A | I | R | C | — | I |
| Déploiement en UAT | I | I | R | C | — | — |
| Go/No-Go déploiement PROD | A | A | R | I | C | I |
| Rollback PROD | A | A | R | I | C | I |
| Gestion des secrets CI/CD | A | I | R | — | — | I |

### 1.4 Gestion des Incidents de Sécurité

| Action | RSSI | Directeur IT | DevOps Lead | Développeur | DBA | Auditeur |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Détection (AlertManager) | R | I | R | I | I | I |
| Classification P1/P2/P3 | R | A | C | I | I | I |
| Activation BCP/DRP | A | A | R | I | C | I |
| Communication client/BCT | A | R | I | — | — | I |
| Forensics et analyse | R | I | C | C | C | R |
| Clôture et PV | R | A | I | — | — | R |
| Rapport DORA Art. 17 | R | A | C | — | — | I |

### 1.5 Données Biométriques (C4 — Critique)

| Action | RSSI | Directeur IT | DevOps Lead | Développeur | DBA | Auditeur | DPO |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Accès aux photos biométriques | A | I | — | — | — | R | R |
| Demande d'effacement (RGPD) | A | I | — | R | R | I | R |
| Modification des politiques | A | A | C | I | — | I | R |
| Audit trail biométrique | R | I | — | — | — | R | R |

---

## 2. PLAN DE FORMATION ANNUEL SÉCURITÉ SI

### 2.1 Calendrier 2026

| Mois | Formation | Public | Durée | Fournisseur | Statut |
|---|---|---|---|---|---|
| Juillet 2026 | Sensibilisation OWASP Top 10 | Tous développeurs | 4h | Interne | 🔴 À planifier |
| Juillet 2026 | RGPD et données biométriques | Toute l'équipe | 2h | DPO externe | 🔴 À planifier |
| Août 2026 | Gestion des secrets (Vault) | DevOps + Dev Lead | 3h | HashiCorp (vidéos) | 🔴 À planifier |
| Septembre 2026 | Procédures DRP (simulation tabletop) | RSSI + DevOps + DBA | 4h | Interne | 🔴 À planifier |
| Octobre 2026 | PCI-DSS v4.0 — Exigences clés | RSSI + Directeur IT | 4h | QSA externe | 🔴 À planifier |
| Novembre 2026 | Sécurité des APIs (OWASP API Top 10) | Tous développeurs | 3h | Interne | 🔴 À planifier |
| Décembre 2026 | Bilan annuel sécurité + mise à jour PSSI | Toute l'équipe | 2h | RSSI | 🔴 À planifier |

### 2.2 Formations Techniques Continues (Obligatoires)

| Compétence | Équipe concernée | Fréquence | Indicateur de réussite |
|---|---|---|---|
| Revue de code sécurisée | Devs + DevOps | Mensuelle (PR review) | 0 finding SAST bloquant |
| Exercices CTF internes | Devs | Trimestrielle | Participation > 80% |
| Veille CVE & patches | DevOps Lead | Hebdomadaire | SLA patch ≤ 72h/CVSS≥9 |
| Tests de phishing simulés | Toute l'équipe | Semestrielle | Taux clic < 5% |

### 2.3 Processus d'Habilitation (On/Off-boarding)

#### On-boarding (Arrivée d'un nouveau collaborateur)

| Étape | Délai | Responsable |
|---|---|---|
| Création compte AD/SSO avec MFA | J0 | DevOps |
| Attribution des droits minimaux (principe du moindre privilège) | J0–J1 | RSSI |
| Formation sécurité obligatoire (2h) | J0–J7 | RSSI |
| Signature de la charte SI | J0–J7 | RH + RSSI |
| Accès progressif selon le rôle | J1–J30 | Manager + RSSI |
| Revue des accès à 3 mois | J90 | RSSI |

#### Off-boarding (Départ d'un collaborateur)

| Étape | Délai | Responsable |
|---|---|---|
| Révocation immédiate des accès SI | J0 (date départ) | DevOps |
| Rotation des secrets partagés connus | J0–J1 | DevOps + RSSI |
| Récupération des équipements | J0 | RH |
| Revue des actions des 30 derniers jours | J0–J7 | RSSI |
| Archivage du compte (90 jours avant suppression) | J0 | DevOps |

---

## 3. PROCÉDURE DE GESTION DES VULNÉRABILITÉS CVE

### SLA de Patch par Sévérité CVSS (Finding BCP-04)

| Sévérité CVSS | Score | SLA de patch | Exemple |
|---|---|---|---|
| **Critique** | 9.0–10.0 | ≤ 72 heures | CVE exploitée en production |
| **Élevé** | 7.0–8.9 | ≤ 7 jours ouvrés | RCE, SQLi critique |
| **Moyen** | 4.0–6.9 | ≤ 30 jours | Fuite d'info, DoS |
| **Faible** | 0.1–3.9 | Planifié (sprint) | Informatif |

### Sources de Veille CVE

- GitHub Dependabot Alerts (automatique — à activer)
- `pip-audit -r requirements.txt` (CI/CD — automatique)
- CERT.tn / CISA Known Exploited Vulnerabilities (hebdomadaire manuel)
- NVD RSS Feed (optionnel)

---

*Document approuvé par : RSSI p.i. / Directeur IT*
*Classification : CONFIDENTIEL — Diffusion interne uniquement*
*Prochaine révision : Décembre 2026*
