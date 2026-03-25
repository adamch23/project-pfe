import { useNavigate } from "react-router-dom";
import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import "./NotFound.css";

export default function NotFound() {
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);

  const handleGoHome = () => {
    if (!user) return navigate("/login");
    if (user.role === "admin") return navigate("/admin");
    return navigate("/dashboard");
  };

  return (
    <div className="notfound-wrapper">
      {/* Grille décorative en arrière-plan */}
      <div className="notfound-grid" aria-hidden="true" />

      {/* Cercles décoratifs */}
      <div className="notfound-orb notfound-orb--1" aria-hidden="true" />
      <div className="notfound-orb notfound-orb--2" aria-hidden="true" />

      <div className="notfound-container">
        {/* Logo */}
        <div className="notfound-brand" onClick={handleGoHome}>
          Attijari<span>bank</span>
        </div>

        {/* Code 404 animé */}
        <div className="notfound-code" aria-label="Erreur 404">
          <span className="notfound-digit">4</span>
          <span className="notfound-zero">
            <span className="notfound-zero-inner">0</span>
          </span>
          <span className="notfound-digit notfound-digit--last">4</span>
        </div>

        {/* Ligne décorative */}
        <div className="notfound-divider">
          <div className="notfound-divider-line" />
          <div className="notfound-divider-dot" />
          <div className="notfound-divider-line" />
        </div>

        {/* Message */}
        <h1 className="notfound-title">Page introuvable</h1>
        <p className="notfound-subtitle">
          La page que vous recherchez n'existe pas ou a été déplacée.<br />
          Vérifiez l'URL ou retournez à votre espace.
        </p>

        {/* Boutons */}
        <div className="notfound-actions">
          <button className="notfound-btn notfound-btn--primary" onClick={handleGoHome}>
            <span className="notfound-btn-icon">←</span>
            Retour à l'accueil
          </button>
          <button className="notfound-btn notfound-btn--secondary" onClick={() => navigate(-1)}>
            Page précédente
          </button>
        </div>

        {/* Code d'erreur */}
        <p className="notfound-code-label">CODE ERREUR : 404 NOT FOUND</p>
      </div>
    </div>
  );
}