import React, { useState, useEffect, useContext } from "react";
import API from "../api/axios"; // Ton instance axios avec token
import { AuthContext } from "../context/AuthContext";
import "./PersonalInfo.css"; // À créer pour le style

const PersonalInfo = () => {
  const { user, setUser } = useContext(AuthContext);

  const [formData, setFormData] = useState({
    name: "",
    email: "",
  });

  const [passwordData, setPasswordData] = useState({
    password: "",
    confirmPassword: "",
  });

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  // ── CHARGEMENT DES INFOS USER ──────────────────────────────
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await API.get("/users/me");
        setFormData({
          name: res.data.name || "",
          email: res.data.email || "",
        });
      } catch (err) {
        console.error(err);
        setMessage("Impossible de charger les informations utilisateur.");
      }
    };
    fetchUser();
  }, []);

  // ── MODIFIER LES INFOS PERSONNELLES ───────────────────────
  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const res = await API.put("/users/me", formData);
      setUser(res.data); // Met à jour le contexte
      setMessage("Profil mis à jour avec succès !");
    } catch (err) {
      console.error(err);
      setMessage(err.response?.data?.detail || "Erreur lors de la mise à jour.");
    }
    setLoading(false);
  };

  // ── MODIFIER LE MOT DE PASSE ─────────────────────────────
  const handleUpdatePassword = async (e) => {
    e.preventDefault();
    setMessage("");

    if (passwordData.password !== passwordData.confirmPassword) {
      setMessage("Les mots de passe ne correspondent pas !");
      return;
    }

    try {
      await API.put("/users/me/password", { password: passwordData.password });
      setPasswordData({ password: "", confirmPassword: "" });
      setMessage("Mot de passe mis à jour avec succès !");
    } catch (err) {
      console.error(err);
      setMessage(err.response?.data?.detail || "Erreur lors de la mise à jour du mot de passe.");
    }
  };

  // ── RENDU ────────────────────────────────────────────────
  return (
    <div className="personal-info-container">
      <h2>Mes Informations</h2>

      {message && <div className="message">{message}</div>}

      {/* ── FORMULAIRE INFOS ── */}
      <form onSubmit={handleUpdateProfile} className="profile-form">
        <label>
          Nom :
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
        </label>
        <label>
          Email :
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            required
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Mise à jour..." : "Mettre à jour mes infos"}
        </button>
      </form>

      {/* ── FORMULAIRE MOT DE PASSE ── */}
      <form onSubmit={handleUpdatePassword} className="password-form">
        <h3>Changer le mot de passe</h3>
        <label>
          Nouveau mot de passe :
          <input
            type="password"
            value={passwordData.password}
            onChange={(e) => setPasswordData({ ...passwordData, password: e.target.value })}
            required
          />
        </label>
        <label>
          Confirmer le mot de passe :
          <input
            type="password"
            value={passwordData.confirmPassword}
            onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
            required
          />
        </label>
        <button type="submit">Changer le mot de passe</button>
      </form>
    </div>
  );
};

export default PersonalInfo;