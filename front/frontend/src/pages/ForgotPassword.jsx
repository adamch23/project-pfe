import { useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/axios";
import "./ForgotPassword.css";

function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Erreur lors de l'envoi du code.";
}

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const validateLocally = () => {
    if (!email.trim()) return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
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
      const res = await API.post("/forgot-password", { email });
      setMessage(res.data?.message || "Email envoyé avec succès !");
      setTimeout(() => navigate(`/reset-password?email=${encodeURIComponent(email)}`), 2000);
    } catch (err) {
      setError(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <h2>Mot de passe oublié</h2>
        <p style={{ color: "#666", fontSize: "14px", marginBottom: "20px" }}>
          Entrez votre email pour recevoir un code de vérification à 6 chiffres.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Ex: client@attijari.tn"
              required
            />
          </div>

          <button type="submit" disabled={loading}>
            {loading ? "Envoi en cours..." : "Envoyer le code"}
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