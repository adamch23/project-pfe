import { createContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/axios";

export const AuthContext = createContext();

function generateNameFromEmail(email) {
  const localPart = email.split("@")[0];
  const parts = localPart.split(/[._]/);
  return parts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Vérifier la session au démarrage (via Cookie HttpOnly) ─────
  useEffect(() => {
    const checkSession = async () => {
      try {
        const res = await API.get("/users/me");
        setUser(res.data);
      } catch (err) {
        setUser(null);
        // Ne pas rediriger ici pour permettre l'accès aux pages publiques (login/signup)
      } finally {
        setLoading(false);
      }
    };
    checkSession();
  }, []);

  // ── Login Step 1 (Credentials) ────────────────────────────────
  const login = async (emailInput, password) => {
    const res = await API.post("/login", { email: emailInput, password });

    if (res.data.mfa_required) {
      return { mfaRequired: true, email: emailInput };
    }

    // Fallback si le MFA n'est pas activé (ne devrait pas arriver en PROD)
    await finalizeLogin(res.data);
    return { mfaRequired: false };
  };

  // ── Login Step 2 (OTP) ──────────────────────────────────────────
  const verifyOtp = async (email, code) => {
    const res = await API.post("/login/verify-otp", { email, code });
    await finalizeLogin(res.data);
  };

  const finalizeLogin = async (loginData) => {
    const { role, has_face_photo } = loginData;
    const userRes = await API.get("/users/me");
    setUser(userRes.data);

    if (has_face_photo) {
      navigate("/face-verify");
    } else if (role === "admin") {
      navigate("/admin");
    } else {
      navigate("/dashboard");
    }
  };

  // ── Appelé après succès de la vérification faciale ──────────
  const completeFaceVerification = () => {
    if (!user) return;
    if (user.role === "admin") navigate("/admin");
    else navigate("/dashboard");
  };

  // ── Mettre à jour le profil dans le contexte ─────────────────
  const updateUserContext = (updates) => {
    setUser(prev => ({ ...prev, ...updates }));
  };

  // ── Logout ────────────────────────────────────────────────────
  const logout = async () => {
    try {
      await API.post("/logout");
    } catch (err) {
      console.error("Erreur lors de la déconnexion serveur", err);
    }
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, login, verifyOtp, logout, loading, completeFaceVerification, updateUserContext }}>
      {children}
    </AuthContext.Provider>
  );
};
