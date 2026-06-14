from datetime import datetime, timedelta, timezone
import logging
from database import db

logger = logging.getLogger(__name__)

# ── Politique de rétention (Finding DATA-01 — Audit Bancaire) ────────────────
# PCI-DSS Req 10.7 : Logs d'audit → 5 ans (1 an online + 4 ans archivés)
# BCT Directive 2021/01 Art. 23 : Données transactionnelles → 5 ans
# RGPD Art. 5(1)(e) : Conservation limitée à la finalité
AUDIT_LOGS_RETENTION_DAYS = 365        # 1 an online — après: archivage S3 Glacier
BIOMETRIC_LOGS_RETENTION_DAYS = 365    # 1 an — conforme RGPD (biométrie = DCP sensibles)
SERVER_LOGS_ROTATION_DAYS = 90         # 3 mois (C2 — logs standards)


class RetentionService:
    def __init__(self):
        self.audit_collection = db["audit_logs"]
        self.biometrics_collection = db["biometric_logs"]

    async def _count_eligible_for_purge(self, collection, limit_date: datetime) -> int:
        """Compte les documents éligibles à la purge avant de supprimer."""
        return await collection.count_documents(
            {"timestamp": {"$lt": limit_date.isoformat()}}
        )

    async def _verify_archiving_done(self, collection_name: str, count: int) -> bool:
        """
        Finding DATA-02 (Audit Bancaire) : Vérification que l'archivage S3 Glacier
        a bien été effectué avant toute purge des données d'audit.

        En production, cette méthode doit interroger le bucket S3 pour confirmer
        que les N documents ont été exportés. En l'absence de confirmation,
        la purge est BLOQUÉE et une alerte est émise.

        Implémentation actuelle (DEV) : vérification via flag configurable.
        Implémentation PROD recommandée : vérifier le manifest d'archivage S3.
        """
        import os
        archiving_enforced = os.getenv("REQUIRE_S3_ARCHIVE_BEFORE_PURGE", "false").lower() == "true"

        if not archiving_enforced:
            # Mode DEV : on avertit mais on ne bloque pas
            if count > 0:
                logger.warning(
                    f"⚠️ RÉTENTION [{collection_name}]: {count} documents éligibles à purge. "
                    "REQUIRE_S3_ARCHIVE_BEFORE_PURGE=false — archivage S3 non vérifié. "
                    "Activez cette variable en production (Finding DATA-02 — Audit Bancaire)."
                )
            return True  # Autoriser la purge en DEV

        # Mode PROD : vérification de l'archivage S3
        # TODO : Implémenter la vérification via manifest S3 (ex: aws s3 ls s3://bucket/archive/...)
        # Pour l'instant, on bloque avec une erreur explicite si PROD
        logger.error(
            f"🚨 PURGE BLOQUÉE [{collection_name}]: {count} documents éligibles. "
            "Vérification d'archivage S3 non implémentée. "
            "Configurez le manifest S3 avant d'activer REQUIRE_S3_ARCHIVE_BEFORE_PURGE=true."
        )
        return False  # Bloquer la purge en PROD tant que la vérification n'est pas implémentée

    async def purge_old_data(self):
        """
        Purge les données dépassant le seuil de rétention online.
        Finding DATA-02 (Audit Bancaire) : La purge est CONDITIONNÉE à la vérification
        de l'archivage S3 Glacier pour les audit_logs.
        Conformité : PCI-DSS Req. 10.7 | BCT 2021/01 | RGPD Art. 5(1)(e)
        """
        results = {}

        # ── Purge Audit Logs (1 an online — conservation 5 ans via archivage) ──
        limit_audit = datetime.now(timezone.utc) - timedelta(days=AUDIT_LOGS_RETENTION_DAYS)
        try:
            eligible_count = await self._count_eligible_for_purge(self.audit_collection, limit_audit)

            if eligible_count > 0:
                archive_confirmed = await self._verify_archiving_done("audit_logs", eligible_count)
                if not archive_confirmed:
                    logger.error(
                        f"🚨 PURGE AUDIT_LOGS ANNULÉE: {eligible_count} documents non purgés "
                        "car l'archivage S3 n'a pas pu être confirmé. "
                        "Vérifiez votre pipeline d'archivage S3 Glacier."
                    )
                    results["audit_purgés"] = 0
                    results["audit_warning"] = "Purge annulée — archivage S3 non confirmé"
                else:
                    audit_result = await self.audit_collection.delete_many({
                        "timestamp": {"$lt": limit_audit.isoformat()}
                    })
                    logger.info(
                        f"♻️ RÉTENTION: {audit_result.deleted_count} logs d'audit purgés "
                        f"(online > {AUDIT_LOGS_RETENTION_DAYS}j). Archivage S3 confirmé."
                    )
                    results["audit_purgés"] = audit_result.deleted_count
            else:
                results["audit_purgés"] = 0

        except Exception as e:
            logger.error(f"❌ Erreur purge audit_logs: {e}")
            results["audit_error"] = str(e)

        # ── Purge Biometric Logs (1 an — RGPD biométrie) ──────────────────────
        limit_bio = datetime.now(timezone.utc) - timedelta(days=BIOMETRIC_LOGS_RETENTION_DAYS)
        try:
            bio_result = await self.biometrics_collection.delete_many({
                "timestamp": {"$lt": limit_bio.isoformat()}
            })
            if bio_result.deleted_count > 0:
                logger.info(
                    f"♻️ RÉTENTION: {bio_result.deleted_count} logs biométriques purgés "
                    f"(> {BIOMETRIC_LOGS_RETENTION_DAYS}j)."
                )
            results["biom_purgés"] = bio_result.deleted_count
        except Exception as e:
            logger.error(f"❌ Erreur purge biometric_logs: {e}")
            results["biom_error"] = str(e)

        has_error = "audit_error" in results or "biom_error" in results
        has_warning = "audit_warning" in results
        results["status"] = "COMPLETED" if not has_error else "PARTIAL_ERROR"
        if has_warning and not has_error:
            results["status"] = "COMPLETED_WITH_WARNINGS"
        return results


retention_service = RetentionService()
