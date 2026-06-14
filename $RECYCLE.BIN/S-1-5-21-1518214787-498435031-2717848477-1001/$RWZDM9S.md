# 📑 RAPPORT D'AUDIT SYSTÈMES D'INFORMATION (NIVEAU DIRECTOR / PARTNER)

**Client :** Plateforme Anomaly Detection AI
**Auditeur :** Senior Lead Auditor (Ex-Big 4)
**Date :** 11 Juin 2026
**Référentiels :** ISO 27001, DORA, PCI-DSS v4.0, RGPD

---

## 1. GOUVERNANCE & CONFORMITÉ RÉGLEMENTAIRE
▸ **Constat (Finding) :** Absence de PSSI (Politique de Sécurité) et de cartographie de conformité à la directive **DORA** (Digital Operational Resilience Act).  
▸ **Statut :** ⚠️ **INITIALISÉ** (Ébauche de modèle d'hygiène .env créée).  
▸ **Niveau de risque :** **ÉLEVÉ**  
▸ **Référentiel violé :** ISO 27001 A.5.1, DORA Chap. II Sec. 2.  
▸ **Recommandation :** Rédiger la PSSI et soumettre un plan de continuité à l'autorité de tutelle.  
▸ **Délai de remédiation :** 90j

---

## 2. ARCHITECTURE & RÉSILIENCE (TIER 3)
▸ **Constat (Finding) :** Redondance backend assurée par `replicas: 2`. Cependant, le point unique de défaillance (SPOF) restait le nœud Docker unique.  
▸ **Statut :** ✅ **EN COURS** (Image Docker sécurisée en mode non-root pour limiter l'impact d'une compromission).  
▸ **Niveau de risque :** **MOYEN**  
▸ **Référentiel violé :** Tier III Uptime Institute (Concurrenly Maintainable).  
▸ **Recommandation :** Migrer vers un cluster Kubernetes (K8s) sur deux zones de disponibilité (AZ) distinctes.  
▸ **Délai de remédiation :** 180j

---

## 3. SÉCURITÉ APPLICATIVE (BANK GRADE)
▸ **Constat (Finding) :** Secrets critiques (SMTP, Clés de chiffrement) étaient exposés.  
▸ **Statut :** ✅ **REMÉDIÉ (Partiel)** : 
  1. Mise en place de `.gitignore` et `.env.example` pour l'hygiène des secrets.
  2. Renforcement du déchiffrement (`security_service.py`) : suppression des retours en clair sur erreur.
▸ **Niveau de risque :** **DIMINUÉ (Moyen)**
▸ **Référentiel violé :** PCI-DSS v4.0 req 6.3.3, OWASP A07:2021.  
▸ **Recommandation :** Déploiement final d'un coffre-fort de secrets (HashiCorp Vault) et MFA.  
▸ **Délai de remédiation :** 30j (MFA).

---

## 4. MATURITÉ DES PROCESSUS (CMMI NIVEAU 3)
▸ **Constat (Finding) :** Couverture de tests automatisés critique (< 20%). Absence de pipeline CI/CD intégrant des scans de sécurité statiques (SAST).  
▸ **Niveau de risque :** **ÉLEVÉ**  
▸ **Référentiel violé :** ISO 27001 A.14.2.2.  
▸ **Recommandation :** Atteindre 80% de couverture de code et automatiser les revues de sécurité en CI/CD.  
▸ **Délai de remédiation :** 90j

---

## 5. CONTINUITÉ D'ACTIVITÉ & GESTION DES INCIDENTS
▸ **Constat (Finding) :** Monitoring robuste via Prometheus/Grafana actif. Cependant, aucun test de basculement (Failover) n'est documenté pour valider le RTO/RPO.  
▸ **Niveau de risque :** **MOYEN**  
▸ **Référentiel violé :** ISO 22301, Bâle III.  
▸ **Recommandation :** Organiser un exercice de reprise d'activité (DRP) et automatiser le calcul du MTTR.  
▸ **Délai de remédiation :** 180j

---

## 6. GESTION DES DONNÉES & CONFIDENTIALITÉ
▸ **Constat (Finding) :** Chiffrement AES-256 et audit trail avec signature HMAC implémentés (Niveau Bancaire). Manque une politique de purge automatique (Retention).  
▸ **Niveau de risque :** **FAIBLE**  
▸ **Référentiel violé :** RGPD Article 17, Article 32.  
▸ **Recommandation :** Implémenter un script de purge automatique des logs obsolètes.  
▸ **Délai de remédiation :** 180j

---

## SYNTHÈSE DES SCORES (SCORE DE MATURITÉ /5)

| Domaine | Score | Statut |
| :--- | :---: | :--- |
| Gouvernance | 2 | ⚠️ |
| Architecture | 3.5 | ✅ |
| Sécurité | 3 | 🚨 |
| Processus | 2 | ⚠️ |
| Continuité | 3.5 | ✅ |
| Données | 4 | ✅ |

**AVIS GLOBAL : CONFORME SOUS RÉSERVE**

---

## ROADMAP DE REMÉDIATION (12 MOIS)

1. **Mois 1 :** Correction critique (Vault + MFA).
2. **Mois 3 :** Qualité logicielle (Tests 80% + CI/CD).
3. **Mois 6 :** Gouvernance (PSSI + DORA).
4. **Mois 12 :** Résilience Tier 3 (Kubernetes Hybrid Cloud).
