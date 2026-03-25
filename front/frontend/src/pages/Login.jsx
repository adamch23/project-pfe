import { useState, useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import "./login.css";

// ── Helper : extrait le message d'erreur de la réponse API ─────────
function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Échec de l'authentification. Veuillez vérifier vos accès.";
}

export default function Login() {
  const { login } = useContext(AuthContext);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  // Validation locale avant envoi
  const validateLocally = () => {
    if (!email.trim()) return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
    if (!password.trim()) return "Le mot de passe est requis";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");

    const localError = validateLocally();
    if (localError) {
      setMessage(localError);
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setMessage(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page-wrapper">
      <div className="login-container">
        <div className="brand-logo">
          Attijari<span>bank</span>
        </div>

        <h1>Espace Sécurisé</h1>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Identifiant / Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Ex: client@attijari.tn"
              required
            />
          </div>

          <div className="input-group">
            <label>Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {message && (
            <div className="error-box">
              <span className="error-icon">⚠️</span>
              <p className="error-message">{message}</p>
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-login">
            {loading ? "Vérification..." : "Accéder à mes comptes"}
          </button>
        </form>

        <div className="footer-links">
          <a href="/forgot-password">Mot de passe oublié ?</a>
          <a href="/signup">S'inscrire</a>
        </div>

        <div className="security-notice">
          <p>Connexion sécurisée SSL 256-bit</p>
          <p>Ne communiquez jamais vos codes confidentiels.</p>
        </div>
      </div>
    </div>
  );
}