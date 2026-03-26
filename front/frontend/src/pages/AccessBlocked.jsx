/**
 * AccessBlocked.jsx
 * ─────────────────────────────────────────────────────────────
 * Overlay plein écran affiché quand la surveillance faciale
 * ne détecte plus le visage de l'utilisateur.
 * Disparaît automatiquement dès que le visage est re-détecté.
 * ─────────────────────────────────────────────────────────────
 */
import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import "./AccessBlocked.css";

export default function AccessBlocked() {
  const { logout } = useContext(AuthContext);

  return (
    <div className="ab-overlay">
      <div className="ab-card">

        {/* Icône animée */}
        <div className="ab-icon-wrap">
          <div className="ab-pulse" />
          <div className="ab-pulse ab-pulse--2" />
          <div className="ab-icon">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="32" cy="22" r="12" stroke="currentColor" strokeWidth="2.5" />
              <path d="M10 54c0-12.15 9.85-22 22-22s22 9.85 22 22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              <line x1="20" y1="20" x2="44" y2="44" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" />
              <line x1="44" y1="20" x2="20" y2="44" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </div>
        </div>

        {/* Texte */}
        <h1 className="ab-title">Accès Suspendu</h1>
        <p className="ab-subtitle">Surveillance biométrique active</p>

        <div className="ab-divider" />

        <p className="ab-message">
          Votre visage n'est plus détecté devant la caméra.<br />
          <strong>Regardez l'écran</strong> pour reprendre l'accès automatiquement.
        </p>

        {/* Indicateur de scan */}
        <div className="ab-scan-bar">
          <div className="ab-scan-line" />
          <span className="ab-scan-label">Recherche du visage en cours...</span>
        </div>

        {/* Bouton déconnexion */}
        <button className="ab-logout-btn" onClick={logout}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Se déconnecter
        </button>

        <p className="ab-security-note">
          🔒 Vérification locale — aucune donnée transmise
        </p>
      </div>
    </div>
  );
}