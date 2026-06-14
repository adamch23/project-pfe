# 🏛️ MATRICE DE COMPÉTENCES & HABILITATIONS (2026)
# Projet : XAI Anomaly Detection Platform

| Collaborateur | Rôle Projet | Système (OS) | Code (Git) | Secrets (Vault) | Audit (Logs) | Statut Habilitation |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **A. Chemengui** | Lead Architect (Admin) | R/W/X | Owner | Admin | Full Access | ✅ VALIDÉ (Niv 3) |
| **B. Consultant Big4** | Auditeur Externe | R | R | No Access | Read Only | ✅ TEMPORAIRE |
| **C. Dev Ops** | SysAdmin | R/W | Maintainer | Read | No Access | ⚠️ EN ATTENTE |

---

# 🛡️ POLITIQUE RBAC (Role-Based Access Control)

### 1. Rôle : ADMIN
- **Description** : Administrateur système et sécurité.
- **Accès API** : `/api/users/*` (Full), `/api/firewall/*`, `/api/audit/*`.
- **Habilitations** : Activation/Désactivation comptes, Consultation Audit Trail, Changement clés.

### 2. Rôle : EMPLOYER (User)
- **Description** : Analyste de données.
- **Accès API** : `/api/health`, `/api/users/me`, `/api/xai/*`.
- **Habilitations** : Consultation des rapports d'anomalies, self-service profile.

### 3. Rôle : AUDITOR (En cours d'implémentation)
- **Description** : Consultant tiers / Autorité de tutelle.
- **Accès API** : Lecture seule sur logs biométriques et audit trail.

---

# 📥 POLITIQUE DE RÉTENTION DES DONNÉES (GDPR)
- **Logs d'Audit** : 10 ans (Archive) / 1 an (Hot Storage).
- **Données Biométriques (Attempts)** : 6 mois.
- **Photos de Référence** : Effacement immédiat après suppression de compte.
