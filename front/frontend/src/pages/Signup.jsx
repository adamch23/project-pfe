import { useState } from "react";
import API from "../api/axios";
import { useNavigate } from "react-router-dom";
import "./signup.css";

// ── Règles de validation mot de passe (miroir du backend) ──────────
const PASSWORD_RULES = [
  { id: "length",    label: "Au moins 8 caractères",               test: (p) => p.length >= 8 },
  { id: "upper",     label: "Au moins une majuscule",               test: (p) => /[A-Z]/.test(p) },
  { id: "lower",     label: "Au moins une minuscule",               test: (p) => /[a-z]/.test(p) },
  { id: "digit",     label: "Au moins un chiffre",                  test: (p) => /\d/.test(p) },
  { id: "special",   label: "Au moins un caractère spécial (@$!%*?&._-#)", test: (p) => /[@$!%*?&._\-#]/.test(p) },
];

function PasswordStrength({ password }) {
  if (!password) return null;
  const passed = PASSWORD_RULES.filter((r) => r.test(password)).length;
  const colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#27ae60"];
  const labels = ["Très faible", "Faible", "Moyen", "Fort", "Très fort"];

  return (
    <div style={{ marginTop: "6px" }}>
      {/* Barre de progression */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "6px" }}>
        {PASSWORD_RULES.map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: "4px",
              borderRadius: "2px",
              background: i < passed ? colors[passed - 1] : "#ddd",
              transition: "background 0.3s",
            }}
          />
        ))}
      </div>
      <p style={{ fontSize: "12px", color: colors[passed - 1] || "#999", margin: "0 0 6px" }}>
        {labels[passed - 1] || ""}
      </p>
      {/* Checklist des règles */}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {PASSWORD_RULES.map((rule) => {
          const ok = rule.test(password);
          return (
            <li key={rule.id} style={{ fontSize: "12px", color: ok ? "#27ae60" : "#e74c3c", marginBottom: "2px" }}>
              {ok ? "✔" : "✖"} {rule.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Helper : extrait le message d'erreur de la réponse API ─────────
function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Erreur lors de l'inscription";
}

export default function Signup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showPasswordRules, setShowPasswordRules] = useState(false);
  const navigate = useNavigate();

  // Validation locale avant envoi
  const validateLocally = () => {
    if (!email.trim()) return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
    const failedRules = PASSWORD_RULES.filter((r) => !r.test(password));
    if (failedRules.length > 0)
      return `Mot de passe invalide — requis : ${failedRules.map((r) => r.label.toLowerCase()).join(", ")}`;
    if (password !== confirmPassword) return "Les mots de passe ne correspondent pas";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setIsError(false);

    const localError = validateLocally();
    if (localError) {
      setIsError(true);
      setMessage(localError);
      return;
    }

    setLoading(true);
    try {
      await API.post("/signup", { email, password });
      setIsError(false);
      setMessage("Inscription réussie ! Redirection vers la connexion...");
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setIsError(true);
      setMessage(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  const allRulesOk = PASSWORD_RULES.every((r) => r.test(password));

  return (
    <div className="signup-page-wrapper">
      <div className="signup-container">
        <div className="brand-logo">
          Attijari<span>bank</span>
        </div>

        <h1>Créer un compte</h1>

        <form onSubmit={handleSubmit}>
          {/* Email */}
          <div className="input-group">
            <label>Email Professionnel</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Ex: nom@attijari.tn"
              required
            />
          </div>

          {/* Mot de passe + indicateur de force */}
          <div className="input-group">
            <label>Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setShowPasswordRules(true)}
              placeholder="••••••••"
              required
              style={{
                borderColor: password
                  ? allRulesOk ? "#27ae60" : "#e74c3c"
                  : undefined,
              }}
            />
            {showPasswordRules && <PasswordStrength password={password} />}
          </div>

          {/* Confirmation */}
          <div className="input-group">
            <label>Confirmation</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                borderColor: confirmPassword
                  ? confirmPassword === password ? "#27ae60" : "#e74c3c"
                  : undefined,
              }}
            />
            {confirmPassword && confirmPassword !== password && (
              <p style={{ fontSize: "12px", color: "#e74c3c", margin: "4px 0 0" }}>
                ✖ Les mots de passe ne correspondent pas
              </p>
            )}
            {confirmPassword && confirmPassword === password && (
              <p style={{ fontSize: "12px", color: "#27ae60", margin: "4px 0 0" }}>
                ✔ Les mots de passe correspondent
              </p>
            )}
          </div>

          {/* Message global */}
          {message && (
            <div className={`message-box ${isError ? "error" : "success"}`}>
              {message}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-signup">
            {loading ? "Traitement..." : "Créer mon espace"}
          </button>
        </form>

        <div className="footer-links">
          <a href="/login">Déjà inscrit ? Se connecter</a>
        </div>

        <div className="security-notice">
          <p>Données protégées par cryptage SSL 256-bit</p>
          <p>L'activation du compte est soumise à validation admin.</p>
        </div>
      </div>
    </div>
  );
}