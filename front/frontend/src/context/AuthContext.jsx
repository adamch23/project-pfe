import { createContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/axios";

export const AuthContext = createContext();

function generateNameFromEmail(email) {
  const localPart = email.split("@")[0];
  const parts     = localPart.split(/[._]/);
  return parts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  const [user,    setUser]    = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Restaurer la session depuis localStorage ─────────────────
  useEffect(() => {
    const token         = localStorage.getItem("access_token");
    const role          = localStorage.getItem("role");
    const email         = localStorage.getItem("email");
    const name          = localStorage.getItem("name");
    const hasFacePhoto  = localStorage.getItem("has_face_photo") === "true";

    if (token && role && email) {
      setUser({ token, role, email, name: name || generateNameFromEmail(email), has_face_photo: hasFacePhoto });
    }
    setLoading(false);
  }, []);

  // ── Login ─────────────────────────────────────────────────────
  const login = async (emailInput, password) => {
    const res = await API.post("/login", { email: emailInput, password });
    const { access_token, has_face_photo } = res.data;

    localStorage.setItem("access_token",   access_token);
    localStorage.setItem("has_face_photo", String(has_face_photo));

    const userRes = await API.get("/users/me", {
      headers: { Authorization: `Bearer ${access_token}` },
    });

    const { role, email, first_name, last_name } = userRes.data;
    const name = (first_name && last_name)
      ? `${first_name} ${last_name}`
      : userRes.data.name || generateNameFromEmail(email);

    localStorage.setItem("role",  role);
    localStorage.setItem("email", email);
    localStorage.setItem("name",  name);

    const userData = { token: access_token, role, email, name, has_face_photo };
    setUser(userData);

    // ── Si l'user a une photo → vérification faciale avant dashboard
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
    setUser(prev => {
      const updated = { ...prev, ...updates };
      if (updates.name)  localStorage.setItem("name",  updates.name);
      if (updates.email) localStorage.setItem("email", updates.email);
      if (updates.has_face_photo !== undefined)
        localStorage.setItem("has_face_photo", String(updates.has_face_photo));
      return updated;
    });
  };

  // ── Logout ────────────────────────────────────────────────────
  const logout = () => {
    ["access_token", "role", "email", "name", "has_face_photo"].forEach(k =>
      localStorage.removeItem(k)
    );
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, completeFaceVerification, updateUserContext }}>
      {children}
    </AuthContext.Provider>
  );
};