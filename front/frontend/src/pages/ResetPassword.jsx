import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import API from "../api/axios";
import "./ForgotPassword.css";

// ── Règles de validation mot de passe (miroir du backend) ──────────
const PASSWORD_RULES = [
  { id: "length",  label: "Au moins 8 caractères",                        test: (p) => p.length >= 8 },
  { id: "upper",   label: "Au moins une majuscule",                        test: (p) => /[A-Z]/.test(p) },
  { id: "lower",   label: "Au moins une minuscule",                        test: (p) => /[a-z]/.test(p) },
  { id: "digit",   label: "Au moins un chiffre",                           test: (p) => /\d/.test(p) },
  { id: "special", label: "Au moins un caractère spécial (@$!%*?&._-#)",   test: (p) => /[@$!%*?&._\-#]/.test(p) },
];

function PasswordStrength({ password }) {
  if (!password) return null;
  const passed = PASSWORD_RULES.filter((r) => r.test(password)).length;
  const colors = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#27ae60"];
  const labels = ["Très faible", "Faible", "Moyen", "Fort", "Très fort"];

  return (
    <div style={{ marginTop: "6px" }}>
      <div style={{ display: "flex", gap: "4px", marginBottom: "6px" }}>
        {PASSWORD_RULES.map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1, height: "4px", borderRadius: "2px",
              background: i < passed ? colors[passed - 1] : "#ddd",
              transition: "background 0.3s",
            }}
          />
        ))}
      </div>
      <p style={{ fontSize: "12px", color: colors[passed - 1] || "#999", margin: "0 0 6px" }}>
        {labels[passed - 1] || ""}
      </p>
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

function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Erreur lors de la réinitialisation du mot de passe";
}

export default function ResetPassword() {
  const navigate  = useNavigate();
  const location  = useLocation();
  const params    = new URLSearchParams(location.search);
  const emailParam = decodeURIComponent(params.get("email") || "");

  const [email]           = useState(emailParam);
  const [code, setCode]   = useState("");
  const [newPassword, setNewPassword]           = useState("");
  const [confirmPassword, setConfirmPassword]   = useState("");
  const [message, setMessage] = useState("");
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);
  const [showPasswordRules, setShowPasswordRules] = useState(false);

  const validateLocally = () => {
    if (!code.trim()) return "Le code est requis";
    if (!/^\d{6}$/.test(code.trim())) return "Le code doit contenir exactement 6 chiffres";
    const failedRules = PASSWORD_RULES.filter((r) => !r.test(newPassword));
    if (failedRules.length > 0)
      return `Mot de passe invalide — requis : ${failedRules.map((r) => r.label.toLowerCase()).join(", ")}`;
    if (newPassword !== confirmPassword) return "Les mots de passe ne correspondent pas";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    const localError = validateLocally();
    if (localError) {
      setError(localError);
      return;
    }

    setLoading(true);
    try {
      const res = await API.post("/reset-password", {
        email,
        code: code.trim(),
        new_password: newPassword,
      });
      setMessage(res.data?.message || "Mot de passe réinitialisé avec succès !");
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  const allRulesOk = PASSWORD_RULES.every((r) => r.test(newPassword));

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h2>Réinitialiser le mot de passe</h2>
        <p style={{ color: "#666", fontSize: "14px", marginBottom: "20px" }}>
          Un code à 6 chiffres a été envoyé à <strong>{email}</strong>.
        </p>

        <form onSubmit={handleSubmit}>
          {/* Code OTP */}
          <div className="input-group">
            <label>Code reçu par email</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="123456"
              maxLength={6}
              required
              style={{
                letterSpacing: "6px",
                fontWeight: "bold",
                fontSize: "20px",
                textAlign: "center",
                borderColor: code.length === 6 ? "#27ae60" : undefined,
              }}
            />
            {code.length > 0 && code.length < 6 && (
              <p style={{ fontSize: "12px", color: "#e67e22", margin: "4px 0 0" }}>
                {6 - code.length} chiffre(s) manquant(s)
              </p>
            )}
          </div>

          {/* Nouveau mot de passe */}
          <div className="input-group">
            <label>Nouveau mot de passe</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              onFocus={() => setShowPasswordRules(true)}
              placeholder="••••••••"
              required
              style={{
                borderColor: newPassword
                  ? allRulesOk ? "#27ae60" : "#e74c3c"
                  : undefined,
              }}
            />
            {showPasswordRules && <PasswordStrength password={newPassword} />}
          </div>

          {/* Confirmation */}
          <div className="input-group">
            <label>Confirmer le mot de passe</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                borderColor: confirmPassword
                  ? confirmPassword === newPassword ? "#27ae60" : "#e74c3c"
                  : undefined,
              }}
            />
            {confirmPassword && confirmPassword !== newPassword && (
              <p style={{ fontSize: "12px", color: "#e74c3c", margin: "4px 0 0" }}>
                ✖ Les mots de passe ne correspondent pas
              </p>
            )}
            {confirmPassword && confirmPassword === newPassword && (
              <p style={{ fontSize: "12px", color: "#27ae60", margin: "4px 0 0" }}>
                ✔ Les mots de passe correspondent
              </p>
            )}
          </div>

          <button type="submit" disabled={loading}>
            {loading ? "Traitement..." : "Réinitialiser le mot de passe"}
          </button>
        </form>

        {message && <p className="success-message">✔ {message}</p>}
        {error   && <p className="error-message">⚠️ {error}</p>}

        <button
          className="login-redirect-button"
          onClick={() => navigate("/login")}
          style={{
            marginTop: "15px",
            padding: "10px 20px",
            cursor: "pointer",
            backgroundColor: "#4CAF50",
            color: "white",
            border: "none",
            borderRadius: "5px",
          }}
        >
          Retour à la page de connexion
        </button>
      </div>
    </div>
  );
}