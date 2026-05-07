import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import "./AccessBlocked.css";

export default function AccessBlocked() {
  const { logout } = useContext(AuthContext);

  return (
    <div className="ab-overlay">
      <div className="ab-card">
        <div className="ab-top-bar" />

        <span className="ab-brand">Attijari<span>bank</span></span>

        <div className="ab-icon-zone">
          <div className="ab-ring" />
          <div className="ab-ring ab-ring--2" />
          <div className="ab-icon-bg">
            <svg width="34" height="34" viewBox="0 0 64 64" fill="none">
              <circle cx="32" cy="22" r="12" stroke="currentColor" strokeWidth="2.5"/>
              <path d="M10 54c0-12.15 9.85-22 22-22s22 9.85 22 22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              <line x1="20" y1="18" x2="44" y2="46" stroke="#EF4444" strokeWidth="3" strokeLinecap="round"/>
              <line x1="44" y1="18" x2="20" y2="46" stroke="#EF4444" strokeWidth="3" strokeLinecap="round"/>
            </svg>
          </div>
        </div>

        <h1 className="ab-title">Accès Suspendu</h1>
        <span className="ab-badge">Surveillance biométrique active</span>

        <div className="ab-divider" />

        <p className="ab-message">
          Votre visage n'est plus détecté devant la caméra.<br />
          <strong>Regardez l'écran</strong> pour reprendre l'accès automatiquement.
        </p>

        <div className="ab-scan-bar">
          <div className="ab-scan-sweep" />
          <div className="ab-scan-dot" />
          <span className="ab-scan-text">Recherche du visage...</span>
        </div>

        <button className="ab-logout" onClick={logout}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
          </svg>
          Se déconnecter
        </button>

        <span className="ab-note">🔒 Vérification locale — aucune donnée transmise</span>
      </div>
    </div>
  );
}